"""
Module 3 + 4 + 5: Text Processing, Embedding Generation & Vector Store
- Chunks documents with configurable size/overlap
- Generates HuggingFace embeddings
- Stores in FAISS with metadata
"""

from __future__ import annotations

import os
import threading
from typing import List, Dict, Any

from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from app.utils.logging_config import logger
from app.config import settings

# ── Configuration (from centralized settings) ─────────────────────
CHUNK_SIZE = settings.chunk_size
CHUNK_OVERLAP = settings.chunk_overlap
EMBEDDING_MODEL = settings.embedding_model
FAISS_INDEX_PATH = settings.faiss_index_path

# ── Singleton embedding model (thread-safe) ──────────────────────
_embeddings: HuggingFaceEmbeddings | None = None
_embed_lock = threading.Lock()


def get_embeddings() -> HuggingFaceEmbeddings:
    global _embeddings
    if _embeddings is None:
        with _embed_lock:
            if _embeddings is None:
                logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
                _embeddings = HuggingFaceEmbeddings(
                    model_name=EMBEDDING_MODEL,
                    model_kwargs={"device": "cpu"},
                    encode_kwargs={"normalize_embeddings": True},
                )
                logger.success("Embedding model loaded")
    return _embeddings


# ── In-Memory FAISS Cache (thread-safe) ───────────────────────────
# Avoids reloading the index from disk on every query (~200-500ms saving)
_vector_store_cache: FAISS | None = None
_cache_mtime: float = 0
_faiss_lock = threading.Lock()


def _get_cached_vector_store() -> FAISS | None:
    """Return cached FAISS index, reloading only if the file changed. Thread-safe."""
    global _vector_store_cache, _cache_mtime
    index_file = os.path.join(FAISS_INDEX_PATH, "index.faiss")
    if not os.path.exists(index_file):
        _vector_store_cache = None
        return None
    mtime = os.path.getmtime(index_file)
    if _vector_store_cache is None or mtime > _cache_mtime:
        with _faiss_lock:
            # Double-check after acquiring lock
            if _vector_store_cache is None or mtime > _cache_mtime:
                logger.info("Loading FAISS index into memory cache")
                _vector_store_cache = FAISS.load_local(
                    FAISS_INDEX_PATH,
                    get_embeddings(),
                    allow_dangerous_deserialization=True,
                )
                _cache_mtime = mtime
                logger.success("FAISS index cached in memory")
    return _vector_store_cache


def _invalidate_cache() -> None:
    """Force the cache to reload on next access."""
    global _vector_store_cache, _cache_mtime
    with _faiss_lock:
        _vector_store_cache = None
        _cache_mtime = 0


# ── Module 3: Text Chunking ───────────────────────────────────────
def chunk_documents(documents: List[Document]) -> List[Document]:
    """Split documents into overlapping chunks for better context retention."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n\n", "\n\n", "\n", ". ", "! ", "? ", ", ", " ", ""],
    )
    chunks = splitter.split_documents(documents)
    # Attach chunk index to metadata
    for i, chunk in enumerate(chunks):
        chunk.metadata["chunk_id"] = i
    logger.info(f"Created {len(chunks)} chunks from {len(documents)} documents")
    return chunks


# ── Module 4 + 5: Embed & Store in FAISS ─────────────────────────
def embed_and_store(chunks: List[Document]) -> FAISS:
    """
    Generate embeddings for chunks and upsert into FAISS.
    If an existing index exists, it merges the new vectors.
    """
    embeddings = get_embeddings()
    os.makedirs(FAISS_INDEX_PATH, exist_ok=True)
    index_file = os.path.join(FAISS_INDEX_PATH, "index.faiss")

    if os.path.exists(index_file):
        logger.info("Loading existing FAISS index and merging new vectors")
        vector_store = FAISS.load_local(
            FAISS_INDEX_PATH,
            embeddings,
            allow_dangerous_deserialization=True,
        )
        vector_store.add_documents(chunks)
    else:
        logger.info("Creating new FAISS index")
        vector_store = FAISS.from_documents(chunks, embeddings)

    vector_store.save_local(FAISS_INDEX_PATH)
    _invalidate_cache()  # Force reload on next query
    logger.success(f"FAISS index saved -> {FAISS_INDEX_PATH}")
    return vector_store


# ── Module 6: Retrieval Engine ────────────────────────────────────
def retrieve_relevant_chunks(
    query: str,
    top_k: int | None = None,
) -> List[tuple[Document, float]]:
    """
    Retrieve the top-K most similar chunks with similarity scores.
    Returns list of (Document, score) tuples.
    Uses in-memory cache for fast repeated queries.
    """
    k = top_k or settings.top_k_results
    vector_store = _get_cached_vector_store()

    if vector_store is None:
        return []

    results = vector_store.similarity_search_with_relevance_scores(query, k=k)
    return results


# -- Full Pipeline: ingest -> chunk -> embed -> store -----------------
def process_and_store(documents: List[Document]) -> Dict[str, Any]:
    """
    Complete pipeline: chunk documents, embed, and store in FAISS.
    Returns a summary dict.
    """
    chunks = chunk_documents(documents)
    embed_and_store(chunks)
    return {
        "documents_processed": len(documents),
        "chunks_created": len(chunks),
        "index_path": FAISS_INDEX_PATH,
        "sources": list({d.metadata.get("source_name", "unknown") for d in documents}),
    }
