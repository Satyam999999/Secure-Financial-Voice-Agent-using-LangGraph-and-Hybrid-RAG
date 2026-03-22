"""
Hybrid Retriever: BM25 (keyword) + FAISS (semantic) + Cross-Encoder Reranking

Pipeline:
1. BM25 retrieves top-K by keyword match
2. FAISS retrieves top-K by semantic similarity  
3. Merge + deduplicate both result sets
4. Cross-encoder reranks all candidates by relevance to query
5. Confidence score computed from top reranked result
6. Low-confidence retrievals trigger HITL escalation
"""

from langchain_community.retrievers import BM25Retriever
from langchain.retrievers import EnsembleRetriever
from sentence_transformers import CrossEncoder
from langchain.schema import Document
from rag.embedder import get_vectorstore
import config

# ── Cross-encoder reranker (loads once) ──────────────────────
# Lightweight model — good accuracy, fast on CPU
print("[RAG] Loading cross-encoder reranker...")
reranker = CrossEncoder(
    "cross-encoder/ms-marco-MiniLM-L-6-v2",
    max_length=512,
)
print("[RAG] Reranker ready.")

# ── Confidence threshold ──────────────────────────────────────
# Below this score → answer is likely unreliable → trigger HITL
CONFIDENCE_THRESHOLD = 0.3  # tune this based on your PDF quality

# Cache for BM25 retriever (rebuilt when chunks change)
_bm25_retriever  = None
_ensemble        = None
_all_chunks      = []

def build_hybrid_retriever(chunks: list):
    """
    Build BM25 + FAISS ensemble retriever from document chunks.
    Call this once after ingesting the PDF.
    """
    global _bm25_retriever, _ensemble, _all_chunks
    _all_chunks = chunks

    print(f"[RAG] Building BM25 index over {len(chunks)} chunks...")
    _bm25_retriever = BM25Retriever.from_documents(chunks)
    _bm25_retriever.k = config.TOP_K

    faiss_retriever = get_vectorstore().as_retriever(
        search_type="similarity",
        search_kwargs={"k": config.TOP_K},
    )

    # Weight: 60% semantic, 40% keyword
    _ensemble = EnsembleRetriever(
        retrievers=[_bm25_retriever, faiss_retriever],
        weights=[0.4, 0.6],
    )
    print("[RAG] Hybrid retriever ready.")

def get_hybrid_retriever():
    """Return ensemble retriever. Raises if not built yet."""
    if _ensemble is None:
        raise RuntimeError("Hybrid retriever not built. Call build_hybrid_retriever() first.")
    return _ensemble

def rerank_documents(query: str, docs: list[Document], top_n: int = None) -> list[tuple]:
    """
    Rerank documents using cross-encoder.
    Returns list of (doc, score) sorted by relevance descending.
    """
    if not docs:
        return []

    top_n = top_n or len(docs)

    pairs  = [(query, doc.page_content) for doc in docs]
    scores = reranker.predict(pairs)

    ranked = sorted(
        zip(docs, scores),
        key=lambda x: x[1],
        reverse=True,
    )
    return ranked[:top_n]

def get_confidence_score(ranked_docs: list[tuple]) -> float:
    """
    Compute confidence from top reranked document score.
    Cross-encoder scores are logits — normalize to 0-1 range.
    """
    if not ranked_docs:
        return 0.0

    top_score = ranked_docs[0][1]

    # Sigmoid normalization of logit score
    import math
    confidence = 1 / (1 + math.exp(-top_score))
    return round(confidence, 3)