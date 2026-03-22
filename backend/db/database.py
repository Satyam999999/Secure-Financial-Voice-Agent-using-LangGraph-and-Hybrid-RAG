"""
Async PostgreSQL connection using SQLAlchemy 2.0 + asyncpg.
Provides engine, session factory, and Base for all models.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
import config

engine = create_async_engine(
    config.DATABASE_URL,
    echo=False,           # set True to debug SQL queries
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,   # verify connection before use
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

class Base(DeclarativeBase):
    pass

async def get_db():
    """FastAPI dependency — yields DB session, closes after request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def init_db():
    """Create all tables on startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[DB] PostgreSQL tables ready.")