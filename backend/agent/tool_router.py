from langchain_groq import ChatGroq
from langchain.prompts import ChatPromptTemplate
from agent import tools
import config

ROUTING_PROMPT = """You are a banking action classifier.

Given the user's message, decide which tool to call.
Reply with ONLY the tool name — no explanation, no punctuation.

Available tools:
- send_email_statement    : user wants account statement sent to email
- fetch_account_summary   : user wants balance or account details
- escalate_to_human       : user wants human agent, is frustrated, complex issue
- request_callback        : user wants a call back from the bank
- apply_for_loan          : user wants to apply for ANY loan — personal, home, car, education, gold, ANY amount
- none                    : no specific tool needed

IMPORTANT: ANY of these phrases = apply_for_loan:
"I want a loan", "I want loan", "need a loan", "apply for loan",
"loan for X amount", "X lakh loan", "personal loan", "home loan",
"car loan", "education loan", "gold loan", "I want 2 lakhs"

Examples:
"send me my last 3 months statement" → send_email_statement
"what is my balance" → fetch_account_summary
"I want to talk to a human agent" → escalate_to_human
"please call me back" → request_callback
"I want a loan" → apply_for_loan
"I want loan for 2 lakhs" → apply_for_loan
"need personal loan" → apply_for_loan
"apply for home loan" → apply_for_loan
"2 lakh loan" → apply_for_loan
"how do I open an account" → none

Previous tool used: {previous_tool}
Previous tool result: {previous_result}

User message: {message}
Tool:"""

_classifier = None

def _resolve_tool(name: str, *fallback_names: str):
    """Resolve tool callables with backward-compatible fallbacks."""
    if hasattr(tools, name):
        return getattr(tools, name)
    for fallback in fallback_names:
        if hasattr(tools, fallback):
            return getattr(tools, fallback)
    return None

send_email_statement = _resolve_tool("send_email_statement")
fetch_account_summary = _resolve_tool("fetch_account_summary", "get_account_summary")
escalate_to_human = _resolve_tool("escalate_to_human", "handoff_to_human")
request_callback = _resolve_tool("request_callback", "schedule_callback")

def get_classifier():
    global _classifier
    if _classifier is None:
        _classifier = ChatGroq(
            model=config.MODEL_NAME,
            temperature=0,
            groq_api_key=config.GROQ_API_KEY,
            max_tokens=10,
        )
    return _classifier

def route_action(message: str, session_id: str, history: list, user: dict = None) -> dict | None:
    """
    Route an ACTION_REQUEST to the correct tool.
    `history` is passed in already resolved by async caller.
    Returns tool result dict, or None if no tool matched.
    """
    prompt = ChatPromptTemplate.from_template(ROUTING_PROMPT)
    chain = prompt | get_classifier()
    result = chain.invoke({"message": message})
    tool_name = result.content.strip().lower()

    print(f"[ToolRouter] '{message[:50]}' → {tool_name}")

    if tool_name == "send_email_statement":
        email = user.get("email") if user else None
        return send_email_statement(session_id, email=email) if send_email_statement else None
    elif tool_name == "fetch_account_summary":
        return fetch_account_summary(session_id)
    elif tool_name == "escalate_to_human":
        return escalate_to_human(session_id, reason=message, conversation_history=history)
    elif tool_name == "request_callback":
        return request_callback(session_id)

    return None  # fallback to generic ACTION response