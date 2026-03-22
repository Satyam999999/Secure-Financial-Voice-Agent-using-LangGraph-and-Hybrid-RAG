from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
import config

def ingest_pdf(pdf_path: str) -> list:
    """
    Load PDF and split into chunks.
    Returns list of LangChain Document objects.
    """
    loader   = PyPDFLoader(pdf_path)
    raw_docs = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size    = config.CHUNK_SIZE,
        chunk_overlap = config.CHUNK_OVERLAP,
        separators    = ["\n\n", "\n", ".", " ", ""],
    )

    chunks = splitter.split_documents(raw_docs)

    for i, chunk in enumerate(chunks):
        chunk.metadata["chunk_id"] = i
        chunk.metadata["source"]   = pdf_path

    print(f"[Loader] {len(raw_docs)} pages → {len(chunks)} chunks")
    return chunks