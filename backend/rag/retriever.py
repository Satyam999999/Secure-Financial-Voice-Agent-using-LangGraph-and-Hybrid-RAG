"""
Enhanced RAG retriever with:
1. Query expansion (multiple phrasings)
2. Hybrid retrieval (BM25 + FAISS)
3. Cross-encoder reranking
4. Confidence scoring
5. HITL trigger on low confidence
"""

from langchain_groq import ChatGroq
from langchain.prompts import ChatPromptTemplate
from langchain.schema.output_parser import StrOutputParser
from rag.embedder import get_vectorstore
from rag.hybrid_retriever import (
    get_hybrid_retriever,
    rerank_documents,
    get_confidence_score,
    CONFIDENCE_THRESHOLD,
)
from rag.query_expander import expand_query
import config

# ── System prompt ─────────────────────────────────────────────
SYSTEM_PROMPT = """You are a precise banking assistant. You ONLY answer from the provided context.

STRICT RULES:
1. Answer ONLY from the RETRIEVED CONTEXT below. Word for word if needed.
2. If the answer is NOT clearly in the context, respond with:
   "I don't have specific details about that in my knowledge base. Please contact our official banking support or visit your nearest branch."
3. NEVER add generic disclaimers like "procedures may vary" or "verify with official channels" UNLESS that exact text is in the context.
4. NEVER fabricate rates, amounts, timelines, or procedures not in the context.
5. Be direct and specific. No padding. No filler sentences.

{history_context}

RETRIEVED CONTEXT:
{context}

CONFIDENCE: {confidence_label}
"""

def format_docs(docs) -> str:
    """Format docs with page numbers and preview."""
    return "\n\n---\n\n".join(
        f"[Page {d.metadata.get('page', '?')} | Chunk {d.metadata.get('chunk_id', '?')}]\n{d.page_content}"
        for d in docs
    )

def get_llm():
    return ChatGroq(
        model=config.MODEL_NAME,
        temperature=0.1,
        groq_api_key=config.GROQ_API_KEY,
    )

def query_rag(question: str, history_context: str = "") -> dict:
    """
    Enhanced RAG pipeline:
    1. Expand query into multiple phrasings
    2. Retrieve using hybrid BM25 + FAISS for each phrasing
    3. Merge and deduplicate all retrieved docs
    4. Rerank with cross-encoder
    5. Compute confidence score
    6. Generate answer with confidence-aware prompt
    7. Return answer + sources + confidence metadata
    """

    # ── Step 1: Query expansion ───────────────────────────────
    queries = expand_query(question, n=2)

    # ── Step 2: Hybrid retrieval for each query variant ───────
    try:
        retriever = get_hybrid_retriever()
    except RuntimeError:
        # Fallback to pure FAISS if hybrid not built yet
        print("[RAG] Hybrid retriever not ready, falling back to FAISS")
        retriever = get_vectorstore().as_retriever(
            search_kwargs={"k": config.TOP_K}
        )

    all_docs = []
    seen_ids = set()

    for q in queries:
        try:
            docs = retriever.invoke(q)
            for doc in docs:
                chunk_id = doc.metadata.get("chunk_id", id(doc))
                if chunk_id not in seen_ids:
                    seen_ids.add(chunk_id)
                    all_docs.append(doc)
        except Exception as e:
            print(f"[RAG] Retrieval error for query variant: {e}")

    # Ensure we have at least some docs
    if not all_docs:
        print("[RAG] No docs retrieved, falling back to FAISS only")
        all_docs = get_vectorstore().as_retriever(
            search_kwargs={"k": config.TOP_K}
        ).invoke(question)

    print(f"[RAG] Retrieved {len(all_docs)} unique chunks across {len(queries)} query variants")

    # ── Step 3: Rerank with cross-encoder ─────────────────────
    ranked_docs = rerank_documents(question, all_docs, top_n=config.TOP_K)

    # ── Step 4: Confidence scoring ────────────────────────────
    confidence       = get_confidence_score(ranked_docs)
    confidence_label = (
        "HIGH"   if confidence >= 0.65 else
        "MEDIUM" if confidence >= CONFIDENCE_THRESHOLD else
        "LOW"
    )

    print(f"[RAG] Confidence: {confidence:.3f} ({confidence_label})")

    # ── Step 5: Build context from top reranked docs ──────────
    top_docs = [doc for doc, _ in ranked_docs]
    context  = format_docs(top_docs)

    # ── Step 6: Generate answer ───────────────────────────────
    llm    = get_llm()
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", "{question}"),
    ])

    filled = prompt.format_messages(
        context          = context,
        history_context  = history_context,
        confidence_label = confidence_label,
        question         = question,
    )

    answer = llm.invoke(filled).content

    # ── Step 7: Build sources metadata ───────────────────────
    sources = [
        {
            "page":      doc.metadata.get("page", "?"),
            "chunk_id":  doc.metadata.get("chunk_id", "?"),
            "preview":   doc.page_content[:120] + "...",
            "score":     round(float(score), 3),
        }
        for doc, score in ranked_docs
    ]

    return {
        "answer":               answer,
        "sources":              sources,
        "num_chunks_retrieved": len(top_docs),
        "confidence":           confidence,
        "confidence_label":     confidence_label,
        "queries_used":         queries,
    }