"""
Conversation memory backed by Redis.
Replaces the in-memory defaultdict with persistent Redis storage.
Async throughout — compatible with FastAPI async routes.
"""
from db.redis_client import (
    add_turn_redis,
    get_history_redis,
    get_context_string_redis,
    clear_session_redis,
)

async def add_turn(session_id: str, role: str, content: str):
    await add_turn_redis(session_id, role, content)

async def get_history(session_id: str) -> list:
    return await get_history_redis(session_id)

async def get_context_string(session_id: str) -> str:
    return await get_context_string_redis(session_id)

async def clear_session(session_id: str):
    await clear_session_redis(session_id)

# Sync versions for use in background threads (voice pipeline)
def add_turn_sync(session_id: str, role: str, content: str):
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(
                add_turn_redis(session_id, role, content), loop
            ).result(timeout=2)
        else:
            loop.run_until_complete(add_turn_redis(session_id, role, content))
    except Exception as e:
        print(f"[Memory] add_turn_sync error: {e}")

def get_history_sync(session_id: str) -> list:
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return asyncio.run_coroutine_threadsafe(
                get_history_redis(session_id), loop
            ).result(timeout=2)
        else:
            return loop.run_until_complete(get_history_redis(session_id))
    except Exception as e:
        print(f"[Memory] get_history_sync error: {e}")
        return []

def get_context_string_sync(session_id: str) -> str:
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return asyncio.run_coroutine_threadsafe(
                get_context_string_redis(session_id), loop
            ).result(timeout=2)
        else:
            return loop.run_until_complete(get_context_string_redis(session_id))
    except Exception as e:
        print(f"[Memory] get_context_string_sync error: {e}")
        return ""