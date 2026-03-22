# 🏦 Banking Voice Agent

> A production-grade, voice-enabled banking assistant with RAG, LangGraph agents, multi-layer guardrails, real-time voice processing, and human-in-the-loop escalation.

<div align="center">

![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=flat-square&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=black)
![LangGraph](https://img.shields.io/badge/LangGraph-Agent-FF6B35?style=flat-square)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-336791?style=flat-square&logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-7-DC382D?style=flat-square&logo=redis&logoColor=white)
![Groq](https://img.shields.io/badge/Groq-LLaMA3_70B-F55036?style=flat-square)

</div>

---

## Architecture


![Architecture Diagram](./image.png)

---



## Tech Stack

**Backend**
- [FastAPI](https://fastapi.tiangolo.com/) — async REST + WebSocket
- [LangGraph](https://github.com/langchain-ai/langgraph) — StateGraph agent with conditional branching
- [Groq](https://console.groq.com/) — LLaMA3 70B via Language Processing Units
- [HuggingFace sentence-transformers](https://www.sbert.net/) — local embeddings (no API key)
- [FAISS](https://github.com/facebookresearch/faiss) — vector similarity search
- [rank-bm25](https://github.com/dorianbrown/rank_bm25) — keyword retrieval
- [CrossEncoder](https://www.sbert.net/docs/pretrained_cross-encoders.html) — reranking (`ms-marco-MiniLM-L-6-v2`)
- [Faster-Whisper](https://github.com/SYSTRAN/faster-whisper) — speech-to-text
- [RealtimeSTT](https://github.com/KoljaB/RealtimeSTT) — continuous voice input
- [PostgreSQL](https://www.postgresql.org/) + [asyncpg](https://github.com/MagicStack/asyncpg) — primary database
- [Redis](https://redis.io/) — session cache, conversation memory, loan flow state
- [SQLAlchemy 2.0](https://www.sqlalchemy.org/) — async ORM

**Frontend**
- [React 18](https://react.dev/) + [Vite](https://vitejs.dev/)
- [AudioWorklet API](https://developer.mozilla.org/en-US/docs/Web/API/AudioWorklet) — 16kHz PCM capture
- [Web Audio API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API) — TTS playback queue

---

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.10–3.12 | [python.org](https://python.org) |
| Node.js | 18+ | [nodejs.org](https://nodejs.org) |
| PostgreSQL | 15+ | `brew install postgresql@15` |
| Redis | 7+ | `brew install redis` |
| Groq API Key | — | [console.groq.com](https://console.groq.com) |
| ffmpeg | Any | `brew install ffmpeg` |

---

## Quick Start

### 1. Clone

```bash
git clone https://github.com/YOUR_USERNAME/banking-voice-agent.git
cd banking-voice-agent
```

### 2. Start services (macOS)

```bash
brew services start postgresql@15
brew services start redis
```

Create the database:
```bash
psql postgres -c "CREATE DATABASE banking_agent;"
psql postgres -c "CREATE USER banking_user WITH PASSWORD 'banking_pass';"
psql postgres -c "GRANT ALL PRIVILEGES ON DATABASE banking_agent TO banking_user;"
```

### 3. Backend setup

```bash
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**macOS Python 3.12 SSL fix (required once):**
```bash
/Applications/Python\ 3.12/Install\ Certificates.command
python3 -c "import torch; torch.hub.load('snakers4/silero-vad', 'silero_vad', trust_repo=True)"
```

### 4. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```env
# ── Groq (LLM inference) ──────────────────────────────────────
GROQ_API_KEY=gsk_..
MODEL_NAME=llama-3.3-70b-versatile

# ── Embeddings (HuggingFace local — no key needed) ────────────
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

# ── RAG settings ──────────────────────────────────────────────
PDF_PATH=data/banking_policy.pdf
FAISS_INDEX_PATH=data/faiss_index
CHUNK_SIZE=400
CHUNK_OVERLAP=80
TOP_K=5
SMTP_EMAIL=s23784619@gmail.com
SMTP_APP_PASSWORD=leul uqrl gaab uutc
JWT_SECRET=bf963cba27611249ea6e0344b175898a434ecfc0d6fc001c49bb890795947305
# PostgreSQL
DATABASE_URL=postgresql+asyncpg://banking_user:banking_pass@localhost:5432/banking_agent
DATABASE_URL_SYNC=postgresql://banking_user:banking_pass@localhost:5432/banking_agent

# Redis
REDIS_URL=redis://localhost:6379/0

# ── Frontend (Vite) ───────────────────────────────────────────
# Local development
VITE_API_URL=http://localhost:8000


```

### 5. Add your banking PDF

```bash
cp your_banking_policy.pdf data/banking_policy.pdf
```

### 6. Start backend

```bash
cd backend
source venv/bin/activate
uvicorn main:app --port 8000
```

Expected output:
```
[RAG] Loading cross-encoder reranker... Reranker ready.
🐘 Connecting to PostgreSQL... [DB] Tables ready.
🔴 Connecting to Redis... ✅ Redis connected.
📄 Ingesting PDF... 18 pages → 182 chunks
🔀 Building hybrid retriever... Hybrid retriever ready.
✅ All systems ready.
```

### 7. Start frontend

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**

---

## Demo Credentials

| Username | Password | Role |
|----------|----------|------|
| `customer1` | `password123` | Customer |
| `admin` | `admin123` | Admin + Dashboard |

---

## Project Structure

```
banking-voice-agent/
├── backend/
│   ├── api/
│   │   ├── routes.py          # Main chat endpoint (LangGraph wired)
│   │   ├── auth_routes.py     # Login, register, logout
│   │   ├── admin.py           # Stats, escalations, resolve
│   │   ├── voice.py           # Whisper STT + gTTS
│   │   ├── voice_ws.py        # WebSocket real-time voice
│   │   └── stream_routes.py   # SSE streaming
│   ├── agent/
│   │   ├── banking_agent.py   # LangGraph StateGraph agent
│   │   ├── loan_flow.py       # Multi-turn loan application flow
│   │   ├── intent.py          # Intent classifier
│   │   ├── memory.py          # Redis conversation memory
│   │   ├── tools.py           # Tool implementations
│   │   ├── tool_router.py     # LLM tool selector
│   │   └── hitl.py            # HITL trigger logic
│   ├── auth/
│   │   └── auth_handler.py    # JWT + Redis session cache
│   ├── db/
│   │   ├── database.py        # SQLAlchemy async engine
│   │   ├── models.py          # User, Session, Interaction, Escalation
│   │   ├── user_service.py    # User CRUD + seed
│   │   ├── redis_client.py    # Redis client + helpers
│   │   └── pg_logger.py       # PostgreSQL logging + analytics
│   ├── guardrails/
│   │   ├── input_guard.py     # Regex input filter
│   │   └── output_guard.py    # Output scanner
│   ├── rag/
│   │   ├── loader.py          # PDF ingestion + chunking
│   │   ├── embedder.py        # FAISS build/load
│   │   ├── retriever.py       # RAG chain + confidence
│   │   ├── hybrid_retriever.py# BM25 + FAISS + reranker
│   │   └── query_expander.py  # Query expansion
│   ├── config.py
│   ├── main.py
│   └── requirements.txt
├── frontend/
│   ├── public/
│   │   └── pcm-processor.js   # AudioWorklet processor
│   └── src/
│       ├── App.jsx            # Main app UI
│       ├── AdminDashboard.jsx # HITL + analytics
│       ├── VoiceChat.jsx      # Real-time voice UI
│       └── main.jsx
├── data/
│   ├── banking_policy.pdf     # Knowledge base (add yours)
│   └── faiss_index/           # Auto-generated
├── logs/
│   └── interactions.jsonl     # Audit trail
├── docker-compose.yml
├── docker-compose.dev.yml
└── .env.example
```

---

## API Reference

### Auth
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/auth/login` | Login → JWT token |
| `POST` | `/api/v1/auth/register` | Create account |
| `POST` | `/api/v1/auth/logout` | Invalidate session |
| `GET` | `/api/v1/auth/me` | Current user info |

### Chat
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/chat` | Standard chat (returns full response) |
| `POST` | `/api/v1/chat/stream` | SSE streaming (token-by-token) |
| `GET` | `/api/v1/history/{session_id}` | Conversation history |
| `DELETE` | `/api/v1/history/{session_id}` | Clear session memory |

### Voice
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/transcribe` | Audio blob → text (Whisper) |
| `POST` | `/api/v1/speak` | Text → audio stream (gTTS) |
| `WS` | `/api/v1/ws/voice` | Real-time bidirectional voice |

### Admin
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/admin/stats` | Analytics: intents, counts, recent |
| `GET` | `/api/v1/admin/escalations` | List pending escalations |
| `POST` | `/api/v1/admin/escalations/{id}/resolve` | Resolve with agent response |

---

## How the RAG Pipeline Works

```
User query
    │
    ▼
Query Expansion (LLM generates 3 variants)
    │
    ▼
Hybrid Retrieval per variant:
  BM25 (keyword) ──┐
                   ├──▶ Merge + Deduplicate
  FAISS (vector) ──┘
    │
    ▼
Cross-Encoder Reranking (ms-marco-MiniLM-L-6-v2)
    │
    ▼
Confidence Scoring (sigmoid of top logit)
    ├── HIGH  (≥0.65) → answer with confidence
    ├── MEDIUM (≥0.3) → answer with caution note
    └── LOW   (<0.3)  → trigger HITL escalation
    │
    ▼
LLaMA3 70B via Groq (grounded, strict prompt)
    │
    ▼
Output Guardrail (scan for card numbers, OTPs, IFSC)
    │
    ▼
SSE Streaming → Frontend
```

---

## Loan Application Flow

```
User: "I want a personal loan"
  │
  ▼ LangGraph detects apply_for_loan → saves state to Redis
  │
User: "2 lakhs"          → state.loan_amount = "2 lakhs"
User: "45,000/month"     → state.monthly_income = "45000"
User: "Home renovation"  → state.loan_purpose = "Home renovation"
User: "Salaried"         → state.employment = "Salaried"
  │
  ▼ check_eligibility node
  │  → max eligible = 45000 × 20 = ₹9,00,000 ✓
  │  → EMI = ₹4,444/month at 12% p.a. for 5 years
  │
User: "Yes"
  │
  ▼ submit_application → generates LOAN ref → sends confirmation email
```



## Docker 

```bash
# Development with hot reload
docker-compose -f docker-compose.dev.yml up --build

# Production
docker-compose up --build -d
```

---

## License

MIT
