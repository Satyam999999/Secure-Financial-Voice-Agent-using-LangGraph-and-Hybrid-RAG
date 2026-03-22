from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from db.database import get_db
from db.user_service import authenticate_user, get_user_by_username
from db.redis_client import get_cached_session, cache_user_session, invalidate_session
import config

bearer_scheme = HTTPBearer(auto_error=False)

def create_token(username: str, account_id: str, role: str) -> str:
    expire  = datetime.now(timezone.utc) + timedelta(hours=config.JWT_EXPIRE_HOURS)
    payload = {
        "sub":        username,
        "account_id": account_id,
        "role":       role,
        "exp":        expire,
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
        )

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    FastAPI dependency — validates JWT.
    Checks Redis cache first, falls back to DB verification.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Please log in.",
        )

    token = credentials.credentials

    # Check Redis cache first (fast path)
    cached = await get_cached_session(token)
    if cached:
        return cached

    # Decode and verify JWT
    payload = decode_token(token)
    username = payload.get("sub")

    # Verify user still exists and is active in DB
    user = await get_user_by_username(db, username)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or deactivated.",
        )

    user_data = {
        "sub":        str(user.username),
        "user_id":    str(user.id),
        "account_id": user.account_id,
        "full_name":  user.full_name,
        "email":      user.email,
        "role":       user.role,
    }

    # Cache for next requests
    await cache_user_session(token, user_data)
    return user_data

async def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> dict | None:
    """Returns user if token valid, None otherwise."""
    if not credentials:
        return None
    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None