from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_groq import ChatGroq
from langchain.prompts import ChatPromptTemplate
from rag.embedder import get_vectorstore
from rag.retriever import format_docs
from guardrails.input_guard import check_input
from agent.intent import classify_intent
from agent.memory import add_turn, get_context_string
from auth.auth_handler import get_optional_user
from db.pg_logger import log_interaction_pg as log_interaction
import config, uuid, json

router = APIRouter()

class StreamRequest(BaseModel):
    question:   str
    session_id: str | None = None

STREAM_SYSTEM_PROMPT = """You are a helpful and cautious banking assistant.

RULES:
1. Answer ONLY using the provided context below.
2. If the answer is not in the context, say: "I don't have that information in my knowledge base. Please contact our official banking support."
3. Never fabricate account numbers, interest rates, or policy details.
4. Keep answers clear, concise, and professional.
5. Never ask for or mention OTPs, passwords, or PINs.
6. Use the conversation history to understand follow-up questions.

{history_context}

CONTEXT FROM KNOWLEDGE BASE:
{context}
"""

@router.post("/chat/stream")
async def chat_stream(
    request: StreamRequest,
    current_user: dict | None = Depends(get_optional_user),
):
    question   = request.question.strip()
    session_id = request.session_id or str(uuid.uuid4())

    # ── Input guard ──────────────────────────────────────────
    guard = check_input(question)
    if not guard["safe"]:
        async def blocked_stream():
            data = json.dumps({
                "type": "meta",
                "intent": guard["reason"],
                "blocked": True,
                "session_id": session_id,
            })
            yield f"data: {data}\n\n"
            yield f"data: {json.dumps({'type': 'token', 'text': guard['response']})}\n\n"
            yield "data: {\"type\": \"done\"}\n\n"
        return StreamingResponse(blocked_stream(), media_type="text/event-stream")

    # ── Intent check ─────────────────────────────────────────
    intent = classify_intent(question)
    await add_turn(session_id, "user", question)

    # Non-INFO intents: don't stream, return immediately
    if intent != "INFO_QUERY":
        msg = (
            "For actions and requests, please use the main chat endpoint. "
            "I can answer general banking questions here in real-time."
        )
        async def action_stream():
            data = json.dumps({
                "type": "meta",
                "intent": intent,
                "blocked": False,
                "session_id": session_id,
            })
            yield f"data: {data}\n\n"
            yield f"data: {json.dumps({'type': 'token', 'text': msg})}\n\n"
            yield "data: {\"type\": \"done\"}\n\n"
        return StreamingResponse(action_stream(), media_type="text/event-stream")

    # ── RAG retrieval ─────────────────────────────────────────
    vectorstore    = get_vectorstore()
    retriever      = vectorstore.as_retriever(search_kwargs={"k": config.TOP_K})
    retrieved_docs = retriever.invoke(question)
    context        = format_docs(retrieved_docs)
    history_ctx    = await get_context_string(session_id)

    sources = [
        {
            "page":     d.metadata.get("page", "?"),
            "chunk_id": d.metadata.get("chunk_id", "?"),
            "preview":  d.page_content[:120] + "...",
        }
        for d in retrieved_docs
    ]

    # ── Build prompt ──────────────────────────────────────────
    prompt = ChatPromptTemplate.from_messages([
        ("system", STREAM_SYSTEM_PROMPT),
        ("human", "{question}"),
    ])
    filled = prompt.format_messages(
        context=context,
        history_context=history_ctx,
        question=question,
    )

    llm = ChatGroq(
        model=config.MODEL_NAME,
        temperature=0.1,
        groq_api_key=config.GROQ_API_KEY,
        streaming=True,
    )

    # ── Stream generator ──────────────────────────────────────
    async def token_stream():
        full_answer = ""

        # First chunk: metadata (intent, sources, session)
        meta = json.dumps({
            "type":       "meta",
            "intent":     intent,
            "blocked":    False,
            "session_id": session_id,
            "sources":    sources,
            "num_chunks": len(retrieved_docs),
        })
        yield f"data: {meta}\n\n"

        # Stream tokens
        async for chunk in llm.astream(filled):
            token = chunk.content
            if token:
                full_answer += token
                yield f"data: {json.dumps({'type': 'token', 'text': token})}\n\n"

        # Done signal
        yield "data: {\"type\": \"done\"}\n\n"

        # Save to memory + log after streaming completes
        await add_turn(session_id, "assistant", full_answer)
        await log_interaction(
            session_id=session_id,
            question=question,
            intent=intent,
            answer=full_answer,
            num_chunks=len(retrieved_docs),
            sources=sources,
        )

    return StreamingResponse(
        token_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )