"""
User CRUD operations using PostgreSQL.
Replaces the hardcoded DEMO_USERS dict in auth_handler.py.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.models import User
from passlib.context import CryptContext
from datetime import datetime, timezone
import uuid

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,
)

async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    result = await db.execute(
        select(User).where(User.username == username, User.is_active == True)
    )
    return result.scalar_one_or_none()

async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(
        select(User).where(User.email == email, User.is_active == True)
    )
    return result.scalar_one_or_none()

async def get_user_by_id(db: AsyncSession, user_id) -> User | None:
    result = await db.execute(
        select(User).where(User.id == user_id, User.is_active == True)
    )
    return result.scalar_one_or_none()

async def create_user(
    db: AsyncSession,
    username: str,
    email: str,
    full_name: str,
    password: str,
    role: str = "customer",
) -> User:
    user = User(
        username        = username,
        email           = email,
        full_name       = full_name,
        hashed_password = pwd_context.hash(password),
        account_id      = f"ACC{str(uuid.uuid4())[:8].upper()}",
        role            = role,
        is_active       = True,
        is_verified     = True,  # auto-verify for demo
    )
    db.add(user)
    await db.flush()  # get ID without committing
    return user

async def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

async def authenticate_user(db: AsyncSession, username: str, password: str) -> User | None:
    user = await get_user_by_username(db, username)
    if not user:
        return None
    if not await verify_password(password, user.hashed_password):
        return None
    return user

async def seed_demo_users(db: AsyncSession):
    """
    Create demo users if they don't exist.
    Called on server startup.
    """
    demo_users = [
        {
            "username":  "customer1",
            "email":     "customer1@demo.bank",
            "full_name": "Demo Customer",
            "password":  "password123",
            "role":      "customer",
        },
        {
            "username":  "admin",
            "email":     "admin@demo.bank",
            "full_name": "Admin User",
            "password":  "admin123",
            "role":      "admin",
        },
    ]

    for u in demo_users:
        existing = await get_user_by_username(db, u["username"])
        if not existing:
            await create_user(
                db,
                username  = u["username"],
                email     = u["email"],
                full_name = u["full_name"],
                password  = u["password"],
                role      = u["role"],
            )
            print(f"[DB] Created demo user: {u['username']}")
        else:
            print(f"[DB] Demo user already exists: {u['username']}")

    await db.commit()