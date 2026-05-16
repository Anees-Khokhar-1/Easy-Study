"""
API Routes: /api/models
Endpoints for managing LLM provider and model selection.
"""

from __future__ import annotations

import asyncio
from fastapi import APIRouter, HTTPException

from app.schemas import SwitchModelRequest
from app.modules.llm_engine import (
    get_available_models,
    get_active_model,
    set_active_model,
)

router = APIRouter()


@router.get("/models")
async def list_models():
    """
    List all available model providers and their models.
    Also returns the currently active provider/model.
    """
    return get_available_models()


@router.get("/models/active")
async def active_model():
    """Return the currently active provider and model."""
    return get_active_model()


@router.post("/models/switch")
async def switch_model(payload: SwitchModelRequest):
    """
    Switch the active LLM provider and model.
    - **provider**: 'ollama', 'groq', or 'openai'
    - **model**: Model identifier (e.g. 'llama3:latest', 'qwen3-32b', 'gpt-4o-mini')
    """
    try:
        result = await asyncio.to_thread(
            set_active_model, payload.provider, payload.model
        )
        return {
            "status": "success",
            "message": f"Switched to {result['provider']} / {result['model']}",
            **result,
        }
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Failed to switch model: {e}")
