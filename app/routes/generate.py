"""
API Routes: /api/generate/*
Endpoints for AI-powered study tool generation:
  - Flashcards
  - Quizzes
  - Summaries
Rate-limited to prevent LLM abuse (10 requests/minute).
Blocking operations wrapped in asyncio.to_thread.
"""

from __future__ import annotations

import asyncio
from fastapi import APIRouter, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.schemas import FlashcardRequest, QuizRequest, SummaryRequest
from app.modules.study_tools import generate_flashcards, generate_quiz, generate_summary

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


# ── POST /api/generate/flashcards ─────────────────────────────────

@router.post("/generate/flashcards")
@limiter.limit("10/minute")
async def api_generate_flashcards(request: Request, payload: FlashcardRequest):
    """
    Generate AI flashcards from the knowledge base.
    - **topic**: Optional focus topic (uses general if omitted)
    - **count**: Number of flashcards (1-30, default 10)
    """
    try:
        result = await asyncio.to_thread(
            generate_flashcards,
            topic=payload.topic,
            count=payload.count,
        )
        return {"status": "success", **result}
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Flashcard generation failed: {e}")


# ── POST /api/generate/quiz ──────────────────────────────────────

@router.post("/generate/quiz")
@limiter.limit("10/minute")
async def api_generate_quiz(request: Request, payload: QuizRequest):
    """
    Generate a multiple-choice quiz from the knowledge base.
    - **topic**: Optional focus topic
    - **count**: Number of questions (1-20, default 5)
    """
    try:
        result = await asyncio.to_thread(
            generate_quiz,
            topic=payload.topic,
            count=payload.count,
        )
        return {"status": "success", **result}
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Quiz generation failed: {e}")


# ── POST /api/generate/summary ───────────────────────────────────

@router.post("/generate/summary")
@limiter.limit("10/minute")
async def api_generate_summary(request: Request, payload: SummaryRequest):
    """
    Generate a summary of ingested content.
    - **topic**: Optional focus topic
    - **length**: 'short', 'medium', or 'long'
    """
    try:
        result = await asyncio.to_thread(
            generate_summary,
            topic=payload.topic,
            length=payload.length,
        )
        return {"status": "success", **result}
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Summary generation failed: {e}")
