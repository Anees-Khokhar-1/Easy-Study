"""
API Route: /api/health
System health check and status report.
Includes cache stats, database stats, and component availability.
Blocking DB operations wrapped in asyncio.to_thread.
"""

import asyncio
from fastapi import APIRouter
from app.config import settings
from app.modules.cache import query_cache
from app.modules.database import get_chat_stats, get_source_stats

router = APIRouter()


@router.get("/health")
async def health_check():
    """Returns system status including index, cache, and database stats."""
    import os
    index_exists = os.path.exists(
        os.path.join(settings.faiss_index_path, "index.faiss")
    )
    openai_configured = bool(
        settings.openai_api_key.strip()
        and not settings.openai_api_key.startswith("sk-your")
    )

    # Safe DB stats in worker thread (won't block event loop or crash if DB isn't ready)
    try:
        chat_stats, source_stats = await asyncio.to_thread(
            lambda: (get_chat_stats(), get_source_stats())
        )
    except Exception:
        chat_stats = {"total_messages": 0}
        source_stats = {"total_sources": 0}

    return {
        "status": "healthy",
        "system": "Easy-Study RAG System",
        "version": "2.0.0",
        "components": {
            "faiss_index": "ready" if index_exists else "empty (no documents ingested yet)",
            "ollama_model": settings.ollama_model,
            "ollama_url": settings.ollama_base_url,
            "embedding_model": settings.embedding_model,
            "openai_fallback": "configured" if openai_configured else "not configured",
            "gemini_api": "configured" if settings.gemini_api_key.strip() else "not configured",
            "openrouter_api": "configured" if settings.openrouter_api_key.strip() else "not configured",
            "confidence_threshold": settings.confidence_threshold,
            "chunk_size": settings.chunk_size,
            "database": "sqlite (active)",
            "rate_limiting": "enabled (60/min global, 30/min queries, 10/min generation)",
        },
        "cache": query_cache.stats(),
        "database": {
            "chat": chat_stats,
            "sources": source_stats,
        },
    }
