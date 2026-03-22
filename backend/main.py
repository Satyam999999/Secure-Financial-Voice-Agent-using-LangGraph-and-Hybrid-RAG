# Fix SSL certificates on macOS Python 3.12
import ssl, certifi, os
ssl._create_default_https_context = lambda: ssl.create_default_context(cafile=certifi.where())
os.environ["SSL_CERT_FILE"]      = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
from api.voice_ws import router as voice_ws_router
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from db.database import init_db
from db.redis_client import get_redis, close_redis
from db.user_service import seed_demo_users
from db.database import AsyncSessionLocal
from rag.loader import ingest_pdf
from rag.embedder import build_or_load_index
from rag.hybrid_retriever import build_hybrid_retriever
from api.routes import router
from api.auth_routes import router as auth_router
from api.voice import router as voice_router
from api.stream_routes import router as stream_router
from api.admin import router as admin_router
import config

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""

    # ── PostgreSQL ────────────────────────────────────────────
    print("🐘 Connecting to PostgreSQL...")
    await init_db()

    # ── Seed demo users ───────────────────────────────────────
    async with AsyncSessionLocal() as db:
        await seed_demo_users(db)

    # ── Redis ─────────────────────────────────────────────────
    print("🔴 Connecting to Redis...")
    redis = await get_redis()
    pong  = await redis.ping()
    print(f"✅ Redis connected: {pong}")

    # ── RAG pipeline ──────────────────────────────────────────
    if not os.path.exists(config.FAISS_INDEX_PATH):
        print("📄 Ingesting PDF...")
        chunks = ingest_pdf(config.PDF_PATH)
        print(f"✅ {len(chunks)} chunks created. Building FAISS index...")
        build_or_load_index(chunks, force_rebuild=True)
    else:
        print("✅ FAISS index exists. Loading...")
        chunks = ingest_pdf(config.PDF_PATH)
        build_or_load_index([], force_rebuild=False)

    print("🔀 Building hybrid retriever...")
    build_hybrid_retriever(chunks)
    print("✅ All systems ready.")

    yield

    # ── Shutdown ──────────────────────────────────────────────
    print("👋 Shutting down...")
    await close_redis()

app = FastAPI(title="Banking Voice Agent API", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router,       prefix="/api/v1")
app.include_router(auth_router,  prefix="/api/v1/auth")
app.include_router(voice_router, prefix="/api/v1")
app.include_router(stream_router,prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1/admin")
app.include_router(voice_ws_router, prefix="/api/v1")
@app.get("/health")
def health():
    return {
        "status":   "ok",
        "version":  "2.0.0",
        "database": "postgresql",
        "cache":    "redis",
    }