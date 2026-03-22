"""
LangGraph Banking Agent

StateGraph flow:
    START
      │
      ▼
    classify_intent          ← what does the user want?
      │
      ├── INFO_QUERY    →  retrieve_context → generate_answer → END
      │
      ├── ACTION_REQUEST → select_tool → execute_tool → evaluate_result
      │                                                       │
      │                                              ┌────────┴────────┐
      │                                         success           needs_more
      │                                              │                 │
      │                                            END          select_tool (loop)
      │
      ├── SENSITIVE/FRAUD → safety_response → END
      │
      └── CHITCHAT → chitchat_response → END
"""

from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq
from langchain.prompts import ChatPromptTemplate
from typing import TypedDict, Annotated, Any
import operator
import config

from guardrails.input_guard import check_input
from guardrails.output_guard import check_output
from agent.intent import classify_intent, BLOCKED_INTENTS, BLOCKED_RESPONSES, CHITCHAT_RESPONSE
from rag.retriever import query_rag
from agent.tools import (
    send_email_statement,
    fetch_account_summary,
    escalate_to_human,
    request_callback,
)

# ── Agent State ───────────────────────────────────────────────
class AgentState(TypedDict):
    # Input
    question:         str
    session_id:       str
    history_context:  str
    user:             dict

    # Routing
    intent:           str
    blocked:          bool
    block_reason:     str

    # Tool execution
    tool_name:        str
    tool_result:      dict
    tool_attempts:    Annotated[int, operator.add]  # auto-increments
    max_tool_attempts: int

    # RAG
    rag_result:       dict
    confidence_label: str

    # Final output
    answer:           str
    sources:          list
    escalated:        bool
    ref_number:       str | None

# ── LLM ──────────────────────────────────────────────────────
def get_llm():
    return ChatGroq(
        model=config.MODEL_NAME,
        temperature=0.1,
        groq_api_key=config.GROQ_API_KEY,
    )

# ── Node: Input Guard ─────────────────────────────────────────
def input_guard_node(state: AgentState) -> AgentState:
    """Layer 1: Block unsafe inputs before anything runs."""
    guard = check_input(state["question"])
    if not guard["safe"]:
        return {
            **state,
            "blocked":      True,
            "block_reason": guard["reason"],
            "answer":       guard["response"],
            "intent":       guard["reason"],
        }
    return {**state, "blocked": False}

# ── Node: Classify Intent ─────────────────────────────────────
def classify_intent_node(state: AgentState) -> AgentState:
    """Classify what the user wants."""
    intent = classify_intent(state["question"])
    print(f"[Agent] Intent: {intent}")
    return {**state, "intent": intent}

# ── Node: Safety Response ─────────────────────────────────────
def safety_response_node(state: AgentState) -> AgentState:
    """Handle SENSITIVE and FRAUD intents."""
    answer = BLOCKED_RESPONSES.get(state["intent"], BLOCKED_RESPONSES["SENSITIVE"])
    return {
        **state,
        "answer":    answer,
        "blocked":   True,
        "escalated": state["intent"] == "FRAUD",
    }

# ── Node: Chitchat Response ───────────────────────────────────
def chitchat_node(state: AgentState) -> AgentState:
    """Handle casual conversation."""
    return {**state, "answer": CHITCHAT_RESPONSE, "sources": []}

# ── Node: Select Tool ─────────────────────────────────────────
TOOL_SELECTION_PROMPT = """You are a banking action classifier.

Given the user's message, select the most appropriate tool.
Reply with ONLY the tool name — nothing else.

Available tools:
- send_email_statement    : user wants account statement
- fetch_account_summary   : user wants balance or account details
- escalate_to_human       : user wants human agent or is frustrated
- request_callback        : user wants a call back
- apply_for_loan          : user wants to apply for any loan — personal, home, car, education, gold — or mentions any loan amount
- none                    : no specific tool needed

CRITICAL: Any message with "loan", "lakh loan", "want loan", "need loan", "apply loan" = apply_for_loan

Previous tool used: {previous_tool}
Previous tool result: {previous_result}

User message: {question}
Tool:"""

def select_tool_node(state: AgentState) -> AgentState:
    """Use LLM to select which tool to call."""
    llm    = get_llm()
    prompt = ChatPromptTemplate.from_template(TOOL_SELECTION_PROMPT)
    chain  = prompt | llm

    previous_tool   = state.get("tool_name", "none")
    previous_result = str(state.get("tool_result", {}).get("message", ""))[:100]

    result    = chain.invoke({
        "question":        state["question"],
        "previous_tool":   previous_tool,
        "previous_result": previous_result,
    })
    tool_name = result.content.strip().lower()

    valid_tools = {
        "send_email_statement", "fetch_account_summary",
        "escalate_to_human", "request_callback",
        "apply_for_loan", "none"
    }
    if tool_name not in valid_tools:
        tool_name = "none"

    print(f"[Agent] Selected tool: {tool_name}")
    return {**state, "tool_name": tool_name}

# ── Node: Execute Tool ────────────────────────────────────────
def execute_tool_node(state: AgentState) -> AgentState:
    """Execute the selected tool."""
    tool     = state["tool_name"]
    session  = state["session_id"]
    user     = state.get("user", {})
    history  = []  # passed from routes

    print(f"[Agent] Executing tool: {tool}")

    if tool == "send_email_statement":
        email  = user.get("email") if user else None
        result = send_email_statement(session, email=email)

    elif tool == "fetch_account_summary":
        result = fetch_account_summary(session)

    elif tool == "escalate_to_human":
        result = escalate_to_human(session, reason=state["question"], conversation_history=history)

    elif tool == "request_callback":
        result = request_callback(session)

    elif tool == "apply_for_loan":
        # Handled by agentic loan flow — signal to start it
        result = {
            "success":  True,
            "message":  "LOAN_FLOW_START",
            "data":     {"start_loan_flow": True},
        }

    else:
        result = {
            "success": False,
            "message": (
                "I understand you want to perform an action. "
                "Please use the official banking app or visit your nearest branch."
            ),
            "data": {},
        }

    ref = result.get("data", {}).get("ref_number")
    return {
        **state,
        "tool_result":   result,
        "tool_attempts": 1,
        "answer":        result["message"],
        "ref_number":    ref,
        "escalated":     tool == "escalate_to_human",
    }

# ── Node: Evaluate Tool Result ────────────────────────────────
def evaluate_result_node(state: AgentState) -> AgentState:
    """
    Evaluate if tool result is satisfactory.
    If not, may need to try another tool or escalate.
    """
    result   = state.get("tool_result", {})
    attempts = state.get("tool_attempts", 0)

    if result.get("success"):
        return {**state, "answer": result["message"]}

    # Tool failed — if max attempts reached, escalate
    if attempts >= state.get("max_tool_attempts", 2):
        fallback = escalate_to_human(
            state["session_id"],
            reason=f"Tool failed after {attempts} attempts: {state['question']}",
            conversation_history=[],
        )
        return {
            **state,
            "answer":    fallback["message"],
            "escalated": True,
            "ref_number": fallback["data"].get("ref_number"),
        }

    return {**state, "answer": result.get("message", "Action could not be completed.")}

# ── Node: Retrieve Context (RAG) ──────────────────────────────
def retrieve_context_node(state: AgentState) -> AgentState:
    """Run RAG pipeline for INFO_QUERY."""
    try:
        result = query_rag(
            state["question"],
            history_context=state.get("history_context", ""),
        )
        return {
            **state,
            "rag_result":      result,
            "confidence_label": result.get("confidence_label", "HIGH"),
        }
    except Exception as e:
        print(f"[Agent] RAG error: {e}")
        return {
            **state,
            "rag_result": {
                "answer":               "I'm having trouble accessing the knowledge base. Please try again.",
                "sources":              [],
                "num_chunks_retrieved": 0,
                "confidence_label":     "LOW",
            },
            "confidence_label": "LOW",
        }

# ── Node: Generate Answer ─────────────────────────────────────
def generate_answer_node(state: AgentState) -> AgentState:
    """Format final answer from RAG result."""
    rag    = state.get("rag_result", {})
    output = check_output(rag.get("answer", ""))

    return {
        **state,
        "answer":  output["text"],
        "sources": rag.get("sources", []),
        "blocked": not output["safe"] or state.get("blocked", False),
    }

# ── Conditional edges ─────────────────────────────────────────
def route_after_guard(state: AgentState) -> str:
    if state.get("blocked"):
        return "blocked"
    return "continue"

def route_after_intent(state: AgentState) -> str:
    intent = state.get("intent", "INFO_QUERY")
    if intent in BLOCKED_INTENTS:
        return "safety"
    if intent == "CHITCHAT":
        return "chitchat"
    if intent == "ACTION_REQUEST":
        return "action"
    return "info"  # INFO_QUERY default

def route_after_tool_eval(state: AgentState) -> str:
    result   = state.get("tool_result", {})
    attempts = state.get("tool_attempts", 0)
    max_att  = state.get("max_tool_attempts", 2)

    # Loan flow — hand off to agentic loan handler
    if result.get("data", {}).get("start_loan_flow"):
        return "loan_flow"

    if not result.get("success") and attempts < max_att:
        return "retry"

    return "done"

# ── Build the graph ───────────────────────────────────────────
def build_agent_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("input_guard",      input_guard_node)
    graph.add_node("classify_intent",  classify_intent_node)
    graph.add_node("safety_response",  safety_response_node)
    graph.add_node("chitchat",         chitchat_node)
    graph.add_node("select_tool",      select_tool_node)
    graph.add_node("execute_tool",     execute_tool_node)
    graph.add_node("evaluate_result",  evaluate_result_node)
    graph.add_node("retrieve_context", retrieve_context_node)
    graph.add_node("generate_answer",  generate_answer_node)

    # Entry point
    graph.set_entry_point("input_guard")

    # Input guard → route
    graph.add_conditional_edges(
        "input_guard",
        route_after_guard,
        {
            "blocked":  END,
            "continue": "classify_intent",
        }
    )

    # Intent → route to appropriate node
    graph.add_conditional_edges(
        "classify_intent",
        route_after_intent,
        {
            "safety":  "safety_response",
            "chitchat": "chitchat",
            "action":  "select_tool",
            "info":    "retrieve_context",
        }
    )

    # Terminal nodes
    graph.add_edge("safety_response",  END)
    graph.add_edge("chitchat",         END)

    # Tool flow
    graph.add_edge("select_tool",     "execute_tool")
    graph.add_edge("execute_tool",    "evaluate_result")

    graph.add_conditional_edges(
        "evaluate_result",
        route_after_tool_eval,
        {
            "done":      END,
            "retry":     "select_tool",   # loop back with context
            "loan_flow": END,             # loan flow handled separately
        }
    )

    # RAG flow
    graph.add_edge("retrieve_context", "generate_answer")
    graph.add_edge("generate_answer",  END)

    return graph.compile()

# ── Singleton compiled graph ──────────────────────────────────
_agent = None

def get_agent():
    global _agent
    if _agent is None:
        print("[Agent] Compiling LangGraph agent...")
        _agent = build_agent_graph()
        print("[Agent] Agent ready.")
    return _agent

# ── Main entry point ──────────────────────────────────────────
async def run_agent(
    question:        str,
    session_id:      str,
    history_context: str = "",
    user:            dict = None,
) -> dict:
    """
    Run the LangGraph agent.
    Returns dict compatible with existing ChatResponse model.
    """
    agent = get_agent()

    initial_state: AgentState = {
        "question":          question,
        "session_id":        session_id,
        "history_context":   history_context,
        "user":              user or {},
        "intent":            "",
        "blocked":           False,
        "block_reason":      "",
        "tool_name":         "",
        "tool_result":       {},
        "tool_attempts":     0,
        "max_tool_attempts": 2,
        "rag_result":        {},
        "confidence_label":  "HIGH",
        "answer":            "",
        "sources":           [],
        "escalated":         False,
        "ref_number":        None,
    }

    # Run the graph
    import asyncio
    final_state = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: agent.invoke(initial_state)
    )

    return {
        "answer":               final_state.get("answer", "I could not process that request."),
        "intent":               final_state.get("intent", "UNKNOWN"),
        "sources":              final_state.get("sources", []),
        "num_chunks_retrieved": len(final_state.get("sources", [])),
        "blocked":              final_state.get("blocked", False),
        "escalated":            final_state.get("escalated", False),
        "tool_used":            final_state.get("ref_number"),
        "confidence_label":     final_state.get("confidence_label"),
        "start_loan_flow":      final_state.get("tool_result", {}).get("data", {}).get("start_loan_flow", False),
    }