from db.pg_logger import log_escalation_pg
from agent.memory import get_history

# Conditions that trigger HITL escalation
HITL_TRIGGERS = {
    "repeated_blocked":  "User has been blocked 2+ times in this session",
    "explicit_escalation": "User explicitly requested human agent",
    "low_confidence":    "System could not find relevant information",
    "fraud_detected":    "Fraud or suspicious activity detected",
}

def should_escalate(
    intent: str,
    blocked: bool,
    answer: str,
    session_id: str,
    session_blocked_count: int,
) -> tuple[bool, str]:
    """
    Returns (should_escalate: bool, reason: str)
    """
    # Explicit escalation request
    if intent == "ACTION_REQUEST" and any(
        w in answer.lower() for w in ["escalate", "human", "agent", "specialist"]
    ):
        return True, HITL_TRIGGERS["explicit_escalation"]

    # Fraud detected
    if intent in ("FRAUD", "FRAUD_ATTEMPT"):
        return True, HITL_TRIGGERS["fraud_detected"]

    # Repeated blocks in same session (user frustrated)
    if session_blocked_count >= 2:
        return True, HITL_TRIGGERS["repeated_blocked"]

    # Low confidence response from RAG
    low_confidence_phrases = [
        "i don't have that information",
        "please contact our official",
        "i cannot find",
        "not in my knowledge base",
    ]
    if any(p in answer.lower() for p in low_confidence_phrases):
        return True, HITL_TRIGGERS["low_confidence"]

    return False, ""


async def trigger_escalation(session_id: str, reason: str):
    history = await get_history(session_id)
    await log_escalation_pg(session_id, reason, history)
    print(f"[HITL] Escalated | session={session_id[:8]} | reason={reason}")