from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
import config, os

# Global store (singleton pattern)
_vectorstore = None

def get_embeddings():
    """
    Load HuggingFace sentence-transformers embeddings locally.
    No API key required. Model is downloaded once and cached.
    Default: all-MiniLM-L6-v2 (fast, 384-dim, great for Q&A)
    """
    return HuggingFaceEmbeddings(
        model_name=config.EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )

def build_or_load_index(chunks: list, force_rebuild: bool = False):
    """
    Build FAISS index from chunks, or load existing one.
    """
    global _vectorstore

    embeddings = get_embeddings()

    if force_rebuild and chunks:
        print("[Embedder] Building new FAISS index with HuggingFace embeddings...")
        _vectorstore = FAISS.from_documents(chunks, embeddings)
        _vectorstore.save_local(config.FAISS_INDEX_PATH)
        print(f"[Embedder] Index saved to {config.FAISS_INDEX_PATH}")
    else:
        print("[Embedder] Loading existing FAISS index...")
        _vectorstore = FAISS.load_local(
            config.FAISS_INDEX_PATH,
            embeddings,
            allow_dangerous_deserialization=True,
        )

    return _vectorstore

def get_vectorstore():
    """Return the singleton vectorstore. Must call build_or_load_index first."""
    if _vectorstore is None:
        raise RuntimeError("Vectorstore not initialized. Call build_or_load_index first.")
    return _vectorstore
