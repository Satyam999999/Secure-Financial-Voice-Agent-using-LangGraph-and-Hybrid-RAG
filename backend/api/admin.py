from fastapi import APIRouter
from pydantic import BaseModel
from db.pg_logger import get_stats_pg, get_escalations_pg, resolve_escalation_pg

router = APIRouter()

@router.get("/stats")
async def stats():
    try:
        return await get_stats_pg()
    except Exception as e:
        return {
            "error": str(e),
            "total": 0,
            "blocked": 0,
            "flagged": 0,
            "escalations": 0,
            "pending_escalations": 0,
            "blocked_pct": 0,
            "intents": [],
            "recent": [],
        }

@router.get("/escalations")
async def list_escalations(status: str = "pending"):
    try:
        result = await get_escalations_pg(status)
        return {"escalations": result or []}
    except Exception as e:
        return {"escalations": [], "error": str(e)}

class ResolveRequest(BaseModel):
    agent_response: str

@router.post("/escalations/{esc_id}/resolve")
async def resolve(esc_id: int, body: ResolveRequest):
    await resolve_escalation_pg(esc_id, body.agent_response)
    return {"resolved": True, "id": esc_id}