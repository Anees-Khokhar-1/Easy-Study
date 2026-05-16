"""
Pydantic Schemas – Request/Response models for all API endpoints.
Separated from routes for cleaner architecture and reusability.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


# ── Query Schemas ─────────────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000, description="The user's question")
    top_k: Optional[int] = Field(5, ge=1, le=20, description="Number of context chunks to retrieve")
    conversation_id: Optional[str] = Field("", description="Conversation ID for grouping messages")


class QueryResponse(BaseModel):
    answer: str
    question: str
    source: str
    model: str
    provider: str
    confidence: float
    triggered_fallback: bool
    retrieved_chunks: int
    cached: bool = False
    sources: Optional[List[Dict[str, Any]]] = None
    reason: Optional[str] = None


# ── Ingestion Schemas ─────────────────────────────────────────────

class URLIngestRequest(BaseModel):
    url: str = Field(..., min_length=5, description="URL to ingest")
    source_type: Optional[str] = Field(None, description="'url' or 'youtube' (auto-detected if omitted)")


class TextIngestRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=100000, description="Text content to ingest")
    title: Optional[str] = Field("User Notes", max_length=200)


class IngestResponse(BaseModel):
    status: str
    message: str
    documents_processed: int
    chunks_created: int
    index_path: str
    sources: List[str]


# ── Study Tool Schemas ────────────────────────────────────────────

class FlashcardRequest(BaseModel):
    topic: Optional[str] = Field(None, max_length=200)
    count: int = Field(10, ge=1, le=30)


class QuizRequest(BaseModel):
    topic: Optional[str] = Field(None, max_length=200)
    count: int = Field(5, ge=1, le=20)


class SummaryRequest(BaseModel):
    topic: Optional[str] = Field(None, max_length=200)
    length: str = Field("medium", pattern="^(short|medium|long)$")


# ── Model Schemas ─────────────────────────────────────────────────

class SwitchModelRequest(BaseModel):
    provider: str = Field(..., pattern="^(ollama|openai|gemini|openrouter)$", description="LLM provider")
    model: str = Field(..., min_length=1, description="Model identifier")
