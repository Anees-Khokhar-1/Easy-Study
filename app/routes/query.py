"""
API Route: /api/query
Processes user queries through the full RAG pipeline.
Rate-limited. DB writes happen in background for speed.
Blocking operations wrapped in asyncio.to_thread to avoid event loop starvation.

Provides two modes:
  - POST /api/query         → full JSON response (original)
  - GET  /api/query/stream  → SSE streaming (token-by-token, fast first-token)
"""

from __future__ import annotations

import asyncio
import json
import queue
import threading
from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import StreamingResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.schemas import QueryRequest
from app.modules.vector_store import retrieve_relevant_chunks
from app.modules.llm_engine import (
    answer_query,
    answer_query_stream,
    get_active_model,
)
from app.modules.cache import query_cache
from app.modules.database import save_chat_message

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


def _save_to_db_async(question, answer, provider, model, confidence, source, conversation_id):
    """Save chat message to DB in a background thread — never blocks the response."""
    try:
        save_chat_message(
            question=question,
            answer=answer,
            provider=provider,
            model=model,
            confidence=confidence,
            source=source,
            cached=False,
            conversation_id=conversation_id,
        )
    except Exception:
        pass  # DB write failure must never affect the user


def _sync_query_pipeline(question: str, top_k: int) -> dict:
    """
    Synchronous query pipeline — runs in a worker thread via asyncio.to_thread.
    This prevents blocking the event loop during FAISS search + LLM generation.
    """
    # Step 1: Retrieve relevant chunks (CPU-bound FAISS search)
    retrieved = retrieve_relevant_chunks(question, top_k=top_k)

    # Step 2: Generate answer with SELECTED model (network/CPU-bound LLM call)
    result = answer_query(question, retrieved)
    return result


@router.post("/query")
@limiter.limit("30/minute")
async def query_knowledge_base(request: Request, payload: QueryRequest):
    """
    Query the knowledge base using RAG.

    1. Checks response cache for identical recent queries
    2. Searches FAISS for top-K similar chunks
    3. Generates answer via active LLM provider (selected model only)
    4. Returns response immediately
    5. Saves Q&A to SQLite in background thread (non-blocking)

    - **question**: The user's question
    - **top_k**: Number of context chunks to retrieve (default: 5)
    """
    question = payload.question.strip()
    if not question:
        raise HTTPException(400, "question cannot be empty")

    try:
        # Step 0: Check cache (instant, in-memory — safe on event loop)
        active = get_active_model()
        cached = query_cache.get(question, payload.top_k, active["model"])
        if cached is not None:
            cached["cached"] = True
            cached["question"] = question
            return cached

        # Step 1+2: Run blocking pipeline in worker thread (non-blocking)
        result = await asyncio.to_thread(_sync_query_pipeline, question, payload.top_k)
        result["question"] = question
        result["cached"] = False

        # Step 3: Cache successful responses
        if result.get("source") != "error":
            query_cache.put(question, payload.top_k, active["model"], result)

        # Step 4: Save to DB in BACKGROUND (non-blocking — user gets response NOW)
        threading.Thread(
            target=_save_to_db_async,
            args=(
                question,
                result.get("answer", ""),
                result.get("provider", ""),
                result.get("model", ""),
                result.get("confidence", 0.0),
                result.get("source", "direct"),
                payload.conversation_id or "",
            ),
            daemon=True,
        ).start()

        return result

    except Exception as e:
        raise HTTPException(500, f"Query failed: {e}")


# ── SSE Streaming Endpoint ───────────────────────────────────────

def _stream_pipeline_sync(question: str, top_k: int, out_queue: queue.Queue):
    """
    Run the streaming pipeline in a background thread.
    Puts SSE events into a queue for the async generator to yield.
    """
    try:
        retrieved = retrieve_relevant_chunks(question, top_k=top_k)
        for item in answer_query_stream(question, retrieved):
            out_queue.put(item)
    except Exception as e:
        out_queue.put({"type": "error", "content": str(e)})
    finally:
        out_queue.put(None)  # Sentinel: stream finished


async def _sse_event_generator(
    question: str,
    top_k: int,
    conversation_id: str,
):
    """Async generator that yields SSE events from the streaming pipeline."""
    active = get_active_model()

    # ── Check cache first (instant) ──────────────────────────────
    cached = query_cache.get(question, top_k, active["model"])
    if cached is not None:
        cached["cached"] = True
        cached["question"] = question
        yield f"data: {json.dumps({'type': 'cached', **cached})}\n\n"
        return

    # ── Stream from LLM ──────────────────────────────────────────
    out_q: queue.Queue = queue.Queue()
    thread = threading.Thread(
        target=_stream_pipeline_sync,
        args=(question, top_k, out_q),
        daemon=True,
    )
    thread.start()

    full_answer_parts = []
    meta_data = {}

    while True:
        # Poll queue without blocking the event loop
        try:
            item = await asyncio.to_thread(out_q.get, timeout=60)
        except Exception:
            yield f"data: {json.dumps({'type': 'error', 'content': 'Timeout waiting for response'})}\n\n"
            break

        if item is None:
            # Stream finished — send done event
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            break

        if item.get("type") == "meta":
            meta_data = item
            yield f"data: {json.dumps(item)}\n\n"
        elif item.get("type") == "token":
            full_answer_parts.append(item["content"])
            yield f"data: {json.dumps(item)}\n\n"
        elif item.get("type") == "error":
            yield f"data: {json.dumps(item)}\n\n"
            break
        elif item.get("type") == "done":
            yield f"data: {json.dumps(item)}\n\n"
            break

    # ── Post-stream: cache + DB write (non-blocking) ─────────────
    full_answer = "".join(full_answer_parts)
    if meta_data and meta_data.get("source") != "error" and full_answer:
        result_for_cache = {
            "answer": full_answer,
            "source": meta_data.get("source", ""),
            "model": meta_data.get("model", ""),
            "provider": meta_data.get("provider", ""),
            "confidence": meta_data.get("confidence", 0.0),
            "triggered_fallback": False,
            "retrieved_chunks": meta_data.get("retrieved_chunks", 0),
            "sources": meta_data.get("sources"),
        }
        query_cache.put(question, top_k, active["model"], result_for_cache)

        threading.Thread(
            target=_save_to_db_async,
            args=(
                question,
                full_answer,
                meta_data.get("provider", ""),
                meta_data.get("model", ""),
                meta_data.get("confidence", 0.0),
                meta_data.get("source", "direct"),
                conversation_id,
            ),
            daemon=True,
        ).start()


@router.get("/query/stream")
@limiter.limit("30/minute")
async def stream_query(
    request: Request,
    question: str = Query(..., min_length=1, max_length=2000),
    top_k: int = Query(5, ge=1, le=20),
    conversation_id: str = Query(""),
):
    """
    Stream a query response via Server-Sent Events (SSE).
    The frontend receives tokens as they are generated for instant display.

    Event types:
      - `meta`   : metadata (model, source, confidence, sources) — sent first
      - `token`  : a chunk of the answer text
      - `done`   : stream complete
      - `cached` : full cached response (no streaming needed)
      - `error`  : an error occurred
    """
    question = question.strip()
    if not question:
        raise HTTPException(400, "question cannot be empty")

    return StreamingResponse(
        _sse_event_generator(question, top_k, conversation_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
