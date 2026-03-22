"""
PostgreSQL-based interaction logger.
Replaces SQLite logger in db/logger.py.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from db.models import Interaction, Escalation
from db.database import AsyncSessionLocal
from datetime import datetime, timezone
import json

async def log_interaction_pg(
    session_id:       str,
    question:         str,
    intent:           str,
    answer:           str,
    tool_used:        str  = None,
    blocked:          bool = False,
    num_chunks:       int  = 0,
    sources:          list = None,
    confidence:       float = None,
    confidence_label: str  = None,
    flagged:          bool = False,
    flag_reason:      str  = None,
    error:            str  = None,
    response_time_ms: int  = None,
    user_id               = None,
):
    async with AsyncSessionLocal() as db:
        interaction = Interaction(
            session_id       = session_id,
            user_id          = user_id,
            question         = question,
            intent           = intent,
            answer           = answer[:500] if answer else "",
            tool_used        = tool_used,
            blocked          = blocked,
            num_chunks       = num_chunks,
            sources          = sources or [],
            confidence       = confidence,
            confidence_label = confidence_label,
            flagged          = flagged,
            flag_reason      = flag_reason,
            error            = error,
            response_time_ms = response_time_ms,
        )
        db.add(interaction)
        await db.commit()

async def log_escalation_pg(session_id: str, reason: str, conversation: list, user_id=None):
    async with AsyncSessionLocal() as db:
        esc = Escalation(
            session_id   = session_id,
            user_id      = user_id,
            reason       = reason,
            conversation = conversation,
            status       = "pending",
        )
        db.add(esc)
        await db.commit()
        return esc.id

async def get_stats_pg() -> dict:
    async with AsyncSessionLocal() as db:
        total      = await db.scalar(select(func.count(Interaction.id)))
        blocked    = await db.scalar(select(func.count(Interaction.id)).where(Interaction.blocked == True))
        flagged    = await db.scalar(select(func.count(Interaction.id)).where(Interaction.flagged == True))
        escalations = await db.scalar(select(func.count(Escalation.id)))
        pending    = await db.scalar(select(func.count(Escalation.id)).where(Escalation.status == "pending"))

        intent_rows = await db.execute(
            select(Interaction.intent, func.count(Interaction.id).label("cnt"))
            .group_by(Interaction.intent)
            .order_by(desc("cnt"))
        )
        intents = [{"intent": r.intent, "cnt": r.cnt} for r in intent_rows]

        recent_rows = await db.execute(
            select(Interaction)
            .order_by(desc(Interaction.id))
            .limit(20)
        )
        recent = []
        for r in recent_rows.scalars():
            recent.append({
                "session_id": r.session_id,
                "timestamp":  r.timestamp.isoformat() if r.timestamp else "",
                "question":   r.question,
                "intent":     r.intent,
                "blocked":    r.blocked,
                "flagged":    r.flagged,
                "confidence_label": r.confidence_label,
            })

        return {
            "total":               total or 0,
            "blocked":             blocked or 0,
            "flagged":             flagged or 0,
            "escalations":         escalations or 0,
            "pending_escalations": pending or 0,
            "blocked_pct":         round((blocked or 0) / (total or 1) * 100, 1),
            "intents":             intents,
            "recent":              recent,
        }

async def get_escalations_pg(status: str = "pending") -> list:
    async with AsyncSessionLocal() as db:
        rows = await db.execute(
            select(Escalation)
            .where(Escalation.status == status)
            .order_by(desc(Escalation.id))
        )
        result = []
        for r in rows.scalars():
            result.append({
                "id":             r.id,
                "session_id":     r.session_id,
                "timestamp":      r.timestamp.isoformat() if r.timestamp else "",
                "reason":         r.reason or "",
                "conversation":   r.conversation if isinstance(r.conversation, list) else [],
                "status":         r.status,
                "agent_response": r.agent_response,
            })
        return result   # always returns list, never None

async def resolve_escalation_pg(esc_id: int, agent_response: str, resolved_by: str = "agent"):
    async with AsyncSessionLocal() as db:
        esc = await db.get(Escalation, esc_id)
        if esc:
            esc.status         = "resolved"
            esc.agent_response = agent_response
            esc.resolved_at    = datetime.now(timezone.utc)
            esc.resolved_by    = resolved_by
            await db.commit()