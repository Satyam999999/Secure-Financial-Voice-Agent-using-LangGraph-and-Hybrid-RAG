"""
Redis client for:
- Conversation memory (replaces Python defaultdict)
- Session cache (fast JWT validation without DB hit)
- Escalation queue (pub/sub for HITL)
"""
import redis.asyncio as aioredis
import json
import config
LOAN_STATE_TTL = 1800
# ── Connection pool ───────────────────────────────────────────
_redis_client = None

async def save_loan_state(session_id: str, state: dict):
    r   = await get_redis()
    key = f"loan_flow:{session_id}"
    await r.setex(key, LOAN_STATE_TTL, json.dumps(state))

async def get_loan_state(session_id: str) -> dict | None:
    r   = await get_redis()
    key = f"loan_flow:{session_id}"
    raw = await r.get(key)
    return json.loads(raw) if raw else None

async def clear_loan_state(session_id: str):
    r = await get_redis()
    await r.delete(f"loan_flow:{session_id}")
    
async def get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            config.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,
        )
    return _redis_client

async def close_redis():
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None

# ── Conversation memory ───────────────────────────────────────
MEMORY_TTL    = 3600       # 1 hour TTL on conversation memory
MAX_TURNS     = 10         # keep last 10 turns

async def add_turn_redis(session_id: str, role: str, content: str):
    """Append a turn to Redis conversation history."""
    r   = await get_redis()
    key = f"memory:{session_id}"

    turn = json.dumps({"role": role, "content": content})
    await r.rpush(key, turn)
    await r.ltrim(key, -(MAX_TURNS * 2), -1)  # keep last N turns
    await r.expire(key, MEMORY_TTL)

async def get_history_redis(session_id: str) -> list:
    """Get conversation history from Redis."""
    r   = await get_redis()
    key = f"memory:{session_id}"
    raw = await r.lrange(key, 0, -1)
    return [json.loads(t) for t in raw]

async def get_context_string_redis(session_id: str) -> str:
    """Format history as string for RAG prompt injection."""
    history = await get_history_redis(session_id)
    if not history:
        return ""
    lines = ["CONVERSATION HISTORY (for context):"]
    for turn in history:
        prefix = "User" if turn["role"] == "user" else "Assistant"
        lines.append(f"{prefix}: {turn['content']}")
    return "\n".join(lines)

async def clear_session_redis(session_id: str):
    """Delete conversation memory for a session."""
    r = await get_redis()
    await r.delete(f"memory:{session_id}")

# ── Session cache ─────────────────────────────────────────────
SESSION_TTL = 3600 * 8  # 8 hours (matches JWT expiry)

async def cache_user_session(token: str, user_data: dict):
    """Cache decoded JWT payload to avoid DB lookup on every request."""
    r   = await get_redis()
    key = f"session:{token[-20:]}"  # use last 20 chars as key
    await r.setex(key, SESSION_TTL, json.dumps(user_data))

async def get_cached_session(token: str) -> dict | None:
    """Get cached user data from Redis. Returns None if not cached."""
    r   = await get_redis()
    key = f"session:{token[-20:]}"
    raw = await r.get(key)
    return json.loads(raw) if raw else None

async def invalidate_session(token: str):
    """Remove session from cache (on logout)."""
    r   = await get_redis()
    key = f"session:{token[-20:]}"
    await r.delete(key)

# ── Escalation queue ──────────────────────────────────────────
ESCALATION_QUEUE = "escalations:pending"

async def push_escalation(escalation_data: dict):
    """Push escalation to Redis queue for HITL dashboard."""
    r = await get_redis()
    await r.lpush(ESCALATION_QUEUE, json.dumps(escalation_data))

async def pop_escalation() -> dict | None:
    """Pop oldest escalation from queue."""
    r   = await get_redis()
    raw = await r.rpop(ESCALATION_QUEUE)
    return json.loads(raw) if raw else None

async def get_queue_length() -> int:
    """Get number of pending escalations."""
    r = await get_redis()
    return await r.llen(ESCALATION_QUEUE)