from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from db.database import get_db
from db.pg_logger import log_interaction_pg as log_interaction, log_escalation_pg
from rag.retriever import query_rag
from guardrails.input_guard import check_input
from guardrails.output_guard import check_output
from agent.intent import classify_intent, BLOCKED_INTENTS, BLOCKED_RESPONSES, CHITCHAT_RESPONSE
from agent.memory import add_turn, get_history, get_context_string, clear_session
from agent.tool_router import route_action
from agent.hitl import should_escalate, trigger_escalation
from auth.auth_handler import get_optional_user
from collections import defaultdict
from agent.banking_agent import run_agent
from agent.loan_flow import run_loan_flow
from db.redis_client import save_loan_state, get_loan_state, clear_loan_state

import uuid

router = APIRouter()
bearer_scheme = HTTPBearer(auto_error=False)
_session_blocked_count: dict[str, int] = defaultdict(int)

class ChatRequest(BaseModel):
    question:   str
    session_id: str | None = None

class ChatResponse(BaseModel):
    answer:               str
    intent:               str
    sources:              list
    num_chunks_retrieved: int
    blocked:              bool = False
    session_id:           str
    tool_used:            str | None = None
    escalated:            bool = False
    confidence:           float | None = None
    confidence_label:     str | None = None

async def save_chat_session_to_db(token: str, chat_session_id: str, db: AsyncSession):
    """Link chat session ID to the user's DB session record."""
    try:
        from db.models import UserSession
        from sqlalchemy import select
        result = await db.execute(
            select(UserSession).where(UserSession.session_token == token)
        )
        session = result.scalar_one_or_none()
        if session and not session.chat_session_id:
            session.chat_session_id = chat_session_id
            await db.commit()
    except Exception as e:
        print(f"[Routes] save_chat_session error: {e}")
        
@router.post("/chat", response_model=ChatResponse)
async def chat(
    request:      ChatRequest,
    current_user: dict | None = Depends(get_optional_user),
    db:           AsyncSession = Depends(get_db),
    credentials:  HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    question   = request.question.strip()
    session_id = request.session_id or str(uuid.uuid4())
    escalated  = False

    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    if len(question) > 1000:
        raise HTTPException(status_code=400, detail="Question too long.")

    user_label = current_user["sub"] if current_user else "guest"
    print(f"[Chat] user={user_label} session={session_id[:8]}")

    # Save chat session to DB on first message
    if credentials and not request.session_id:
        await save_chat_session_to_db(credentials.credentials, session_id, db)

    # Check if in active loan flow
    loan_state = await get_loan_state(session_id)

    if loan_state:
        # Continue loan flow
        result    = await run_loan_flow(question, session_id, current_user or {}, loan_state)
        answer    = result["answer"]
        ref       = result.get("ref_number")

        if result.get("completed"):
            await clear_loan_state(session_id)
        else:
            await save_loan_state(session_id, result["loan_state"])

        await add_turn(session_id, "user", question)
        await add_turn(session_id, "assistant", answer)
        await log_interaction(
            session_id=session_id, question=question,
            intent="ACTION_REQUEST", answer=answer, tool_used=ref,
        )
        return ChatResponse(
            answer=answer, intent="ACTION_REQUEST",
            sources=[], num_chunks_retrieved=0,
            session_id=session_id, tool_used=ref,
        )

    # Run main LangGraph agent
    history_context = await get_context_string(session_id)

    result = await run_agent(
        question        = question,
        session_id      = session_id,
        history_context = history_context,
        user            = current_user or {},
    )

    # Handle escalation logging
    if result.get("escalated"):
        await log_escalation_pg(session_id, question, await get_history(session_id))
        escalated = True

    # Handle loan flow start
    # Handle loan flow start
    if result.get("start_loan_flow"):
        # Save empty loan state to Redis BEFORE returning
        # so next user message continues the flow
        initial_loan_state = {
            "loan_type":      "unknown",
            "loan_amount":    "unknown",
            "monthly_income": "unknown",
            "loan_purpose":   "unknown",
            "employment":     "unknown",
            "current_step":   "collecting",
        }
        await save_loan_state(session_id, initial_loan_state)
        result["answer"] = "I'd be happy to help you apply for a loan! What type of loan are you looking for? (Personal, Home, Car, Education, or Gold loan)"

    await add_turn(session_id, "user", question)
    await add_turn(session_id, "assistant", result["answer"])
    await log_interaction(
        session_id       = session_id,
        question         = question,
        intent           = result.get("intent", ""),
        answer           = result["answer"],
        tool_used        = result.get("tool_used"),
        blocked          = result.get("blocked", False),
        num_chunks       = result.get("num_chunks_retrieved", 0),
        sources          = result.get("sources", []),
        confidence       = None,
        confidence_label = result.get("confidence_label"),
        flagged          = escalated,
    )

    return ChatResponse(
        answer               = result["answer"],
        intent               = result.get("intent", ""),
        sources              = result.get("sources", []),
        num_chunks_retrieved = result.get("num_chunks_retrieved", 0),
        blocked              = result.get("blocked", False),
        session_id           = session_id,
        tool_used            = result.get("tool_used"),
        escalated            = escalated,
        confidence_label     = result.get("confidence_label"),
    )


@router.get("/history/{session_id}")
async def get_session_history(session_id: str):
    return {"session_id": session_id, "history": await get_history(session_id)}

@router.delete("/history/{session_id}")
async def clear_session_history(session_id: str):
    await clear_session(session_id)
    return {"cleared": True}

@router.get("/health")
def health():
    return {
        "rag": "ready", "guardrails": "active",
        "intent": "active", "memory": "active",
        "tools": "active", "logs": "active", "hitl": "active",
    }