from dotenv import load_dotenv
import os

load_dotenv()
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SMTP_EMAIL        = os.getenv("SMTP_EMAIL")
SMTP_APP_PASSWORD = os.getenv("SMTP_APP_PASSWORD")

def _resolve_path(path_value: str) -> str:
	"""Resolve env paths relative to project root unless already absolute."""
	if os.path.isabs(path_value):
		return path_value
	return os.path.join(BASE_DIR, path_value)

# Groq — used for chat/LLM inference
GROQ_API_KEY       = os.getenv("GROQ_API_KEY")
MODEL_NAME         = os.getenv("MODEL_NAME", "llama-3.3-70b-versatile")

# HuggingFace — used locally for embeddings (no API key needed)
EMBEDDING_MODEL    = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

PDF_PATH           = _resolve_path(os.getenv("PDF_PATH", "data/banking_policy.pdf"))
FAISS_INDEX_PATH   = _resolve_path(os.getenv("FAISS_INDEX_PATH", "data/faiss_index"))
CHUNK_SIZE         = int(os.getenv("CHUNK_SIZE", 400))
CHUNK_OVERLAP      = int(os.getenv("CHUNK_OVERLAP", 80))
TOP_K              = int(os.getenv("TOP_K", 5))
JWT_SECRET        = os.getenv("JWT_SECRET", "change-this-to-a-random-secret-in-production")
JWT_ALGORITHM     = "HS256"
JWT_EXPIRE_HOURS  = int(os.getenv("JWT_EXPIRE_HOURS", 8))
# ── Database ──────────────────────────────────────────────────
DATABASE_URL      = os.getenv("DATABASE_URL", "postgresql+asyncpg://banking_user:banking_pass@localhost:5432/banking_agent")
DATABASE_URL_SYNC = os.getenv("DATABASE_URL_SYNC", "postgresql://banking_user:banking_pass@localhost:5432/banking_agent")

# ── Redis ─────────────────────────────────────────────────────
REDIS_URL         = os.getenv("REDIS_URL", "redis://localhost:6379/0")