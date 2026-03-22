from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from db.database import get_db
from db.user_service import authenticate_user, create_user, get_user_by_username, get_user_by_email
from db.redis_client import invalidate_session
from auth.auth_handler import create_token, get_current_user
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from db.models import UserSession
from datetime import datetime, timezone, timedelta
import config

router = APIRouter()
bearer_scheme = HTTPBearer(auto_error=False)

class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username:  str
    email:     str
    full_name: str
    password:  str

class LoginResponse(BaseModel):
    access_token: str
    token_type:   str
    username:     str
    full_name:    str
    role:         str
    chat_session_id: str | None = None

@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await authenticate_user(db, request.username, request.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    token = create_token(user.username, user.account_id, user.role)

    # Find most recent active session to restore chat_session_id
    from sqlalchemy import select, desc
    result = await db.execute(
        select(UserSession)
        .where(UserSession.user_id == user.id, UserSession.is_active == True)
        .order_by(desc(UserSession.created_at))
        .limit(1)
    )
    last_session    = result.scalar_one_or_none()
    chat_session_id = last_session.chat_session_id if last_session else None

    # Create new UserSession record
    expires_at = datetime.now(timezone.utc) + timedelta(hours=config.JWT_EXPIRE_HOURS)
    new_session = UserSession(
        user_id       = user.id,
        session_token = token,
        chat_session_id = chat_session_id,
        is_active     = True,
        expires_at    = expires_at,
    )
    db.add(new_session)
    await db.commit()

    print(f"[Auth] Login: {user.username} | restored session: {chat_session_id}")

    return LoginResponse(
        access_token    = token,
        token_type      = "bearer",
        username        = user.username,
        full_name       = user.full_name,
        role            = user.role,
        chat_session_id = chat_session_id,
    )

@router.post("/register")
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    # Check username taken
    if await get_user_by_username(db, request.username):
        raise HTTPException(status_code=400, detail="Username already taken.")
    # Check email taken
    if await get_user_by_email(db, request.email):
        raise HTTPException(status_code=400, detail="Email already registered.")

    user = await create_user(
        db,
        username  = request.username,
        email     = request.email,
        full_name = request.full_name,
        password  = request.password,
        role      = "customer",
    )
    await db.commit()
    print(f"[Auth] Registered: {user.username}")
    return {"message": "Account created successfully.", "username": user.username}

@router.post("/logout")
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    current_user: dict = Depends(get_current_user),
):
    if credentials:
        await invalidate_session(credentials.credentials)
    return {"message": "Logged out successfully."}

@router.get("/me")
async def me(current_user: dict = Depends(get_current_user)):
    return current_user