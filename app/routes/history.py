"""
API Routes: /api/history, /api/sources, /api/conversations
Endpoints for chat history, conversations, and ingested source management.
Blocking DB operations wrapped in asyncio.to_thread.
"""

from __future__ import annotations

import asyncio
from fastapi import APIRouter, HTTPException, Query

from app.modules.database import (
    get_chat_history,
    get_chat_stats,
    clear_chat_history,
    get_ingested_sources,
    get_source_stats,
    delete_source,
    create_conversation,
    get_conversations,
    get_conversation_messages,
    delete_conversation,
)

router = APIRouter()


# ── Conversations ─────────────────────────────────────────────────

@router.post("/conversations")
async def new_conversation():
    """Create a new conversation. Returns the conversation ID."""
    conv_id = await asyncio.to_thread(create_conversation)
    return {"id": conv_id, "title": "New Chat"}


@router.get("/conversations")
async def list_conversations(limit: int = Query(30, ge=1, le=100)):
    """List recent conversations, newest first."""
    convos = await asyncio.to_thread(get_conversations, limit=limit)
    return {"conversations": convos}


@router.get("/conversations/{conv_id}")
async def get_conversation(conv_id: str):
    """Get all messages for a specific conversation."""
    messages = await asyncio.to_thread(get_conversation_messages, conv_id)
    return {"conversation_id": conv_id, "messages": messages}


@router.delete("/conversations/{conv_id}")
async def remove_conversation(conv_id: str):
    """Delete a conversation and all its messages."""
    success = await asyncio.to_thread(delete_conversation, conv_id)
    if not success:
        raise HTTPException(404, f"Conversation {conv_id} not found")
    return {"status": "deleted", "conversation_id": conv_id}


# ── Chat History ──────────────────────────────────────────────────

@router.get("/history")
async def list_chat_history(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Retrieve paginated chat history, newest first."""
    messages, stats = await asyncio.to_thread(
        lambda: (get_chat_history(limit=limit, offset=offset), get_chat_stats())
    )
    return {
        "messages": messages,
        "stats": stats,
        "pagination": {"limit": limit, "offset": offset},
    }


@router.delete("/history")
async def delete_chat_history():
    """Clear all chat history."""
    deleted = await asyncio.to_thread(clear_chat_history)
    return {"status": "cleared", "deleted": deleted}


# ── Ingested Sources ──────────────────────────────────────────────

@router.get("/sources")
async def list_sources():
    """List all ingested document sources with statistics."""
    sources, stats = await asyncio.to_thread(
        lambda: (get_ingested_sources(), get_source_stats())
    )
    return {"sources": sources, "stats": stats}


@router.delete("/sources/{source_id}")
async def remove_source(source_id: int):
    """Soft-delete an ingested source by ID."""
    success = await asyncio.to_thread(delete_source, source_id)
    if not success:
        raise HTTPException(404, f"Source {source_id} not found")
    return {"status": "deleted", "source_id": source_id}
