"""
Module 7 + 8 + 9: LLM Response Generation, Confidence Checker & Fallback AI
Supports 4 providers:
  - Ollama     (local, free)
  - Gemini     (cloud, FREE – get key at https://aistudio.google.com/apikey)
  - OpenRouter (cloud, FREE – get key at https://openrouter.ai, runs open-source models)
  - OpenAI     (cloud, paid)
"""

from __future__ import annotations

import threading
from typing import List, Tuple, Dict, Any, Optional

from langchain.schema import Document
from langchain.prompts import PromptTemplate
from app.utils.logging_config import logger
from app.config import settings

# ── Configuration (from centralized settings) ─────────────────────
OLLAMA_BASE_URL = settings.ollama_base_url
OLLAMA_MODEL = settings.ollama_model
OPENAI_API_KEY = settings.openai_api_key
GEMINI_API_KEY = settings.gemini_api_key
OPENROUTER_API_KEY = settings.openrouter_api_key
CONFIDENCE_THRESHOLD = settings.confidence_threshold

# ── Available Model Providers ─────────────────────────────────────
OLLAMA_MODELS = ["llama3:latest", "llama3.1:8b"]

GEMINI_MODELS = {
    "gemini-2.5-flash": "gemini-2.5-flash",
    "gemini-2.0-flash": "gemini-2.0-flash",
    "gemini-2.0-flash-lite": "gemini-2.0-flash-lite",
}

OPENROUTER_MODELS = {
    "auto-free": "openrouter/free",
    "nemotron-120b": "nvidia/nemotron-3-super-120b-a12b:free",
    "gemma-4-31b": "google/gemma-4-31b-it:free",
    "gemma-4-26b": "google/gemma-4-26b-a4b-it:free",
    "qwen3-coder": "qwen/qwen3-coder:free",
    "minimax-m2.5": "minimax/minimax-m2.5:free",
}

# ── Active Model State (thread-safe) ─────────────────────────────
_active_provider = "ollama"
_active_model = OLLAMA_MODEL
_model_lock = threading.Lock()

# ── LLM Client Singletons (thread-safe) ──────────────────────────
_openai_client = None
_openrouter_client = None
_gemini_client = None
_ollama_llm_cache: dict = {}  # model_name -> OllamaLLM instance
_client_lock = threading.Lock()




def _get_openai_client():
    """Thread-safe singleton OpenAI client."""
    global _openai_client
    if _openai_client is None:
        with _client_lock:
            if _openai_client is None:
                from openai import OpenAI
                _openai_client = OpenAI(api_key=OPENAI_API_KEY, timeout=30.0)
    return _openai_client


def _get_openrouter_client():
    """Thread-safe singleton OpenRouter client (OpenAI-compatible)."""
    global _openrouter_client
    if _openrouter_client is None:
        with _client_lock:
            if _openrouter_client is None:
                from openai import OpenAI
                _openrouter_client = OpenAI(
                    api_key=OPENROUTER_API_KEY,
                    base_url="https://openrouter.ai/api/v1",
                    timeout=60.0,
                )
    return _openrouter_client


def _get_gemini_client():
    """Thread-safe singleton Gemini client."""
    global _gemini_client
    if _gemini_client is None:
        with _client_lock:
            if _gemini_client is None:
                from google import genai
                _gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    return _gemini_client


# ── Model Switching ───────────────────────────────────────────────

def set_active_model(provider: str, model: str) -> Dict[str, str]:
    """Switch the active LLM provider and model at runtime."""
    global _active_provider, _active_model
    with _model_lock:
        provider = provider.lower().strip()
        model = model.strip()

        if provider == "ollama":
            _active_provider = "ollama"
            _active_model = model or OLLAMA_MODEL
        elif provider == "openai":
            if not OPENAI_API_KEY or OPENAI_API_KEY.startswith("sk-your"):
                raise ValueError("OPENAI_API_KEY not configured in .env")
            _active_provider = "openai"
            _active_model = model or "gpt-4o-mini"
        elif provider == "gemini":
            if not GEMINI_API_KEY:
                raise ValueError("GEMINI_API_KEY not configured. Get a FREE key at https://aistudio.google.com/apikey")
            _active_provider = "gemini"
            _active_model = GEMINI_MODELS.get(model, model or "gemini-2.0-flash")
        elif provider == "openrouter":
            if not OPENROUTER_API_KEY:
                raise ValueError("OPENROUTER_API_KEY not configured. Get a FREE key at https://openrouter.ai")
            _active_provider = "openrouter"
            _active_model = OPENROUTER_MODELS.get(model, model)
        else:
            raise ValueError(f"Unknown provider: {provider}. Use 'ollama', 'gemini', 'openrouter', or 'openai'.")

        logger.info(f"Switched to {_active_provider} / {_active_model}")
        return {"provider": _active_provider, "model": _active_model}


def get_active_model() -> Dict[str, str]:
    """Return the current active provider and model."""
    return {"provider": _active_provider, "model": _active_model}


def get_available_models() -> Dict[str, Any]:
    """Return all available model providers and their models."""
    models = {
        "ollama": {
            "available": True,
            "models": OLLAMA_MODELS,
            "description": "Local LLM via Ollama (requires Ollama running)",
        },
        "gemini": {
            "available": bool(GEMINI_API_KEY),
            "models": list(GEMINI_MODELS.keys()),
            "description": "Google Gemini API (FREE - get key at aistudio.google.com)",
        },
        "openrouter": {
            "available": bool(OPENROUTER_API_KEY),
            "models": list(OPENROUTER_MODELS.keys()),
            "description": "OpenRouter (FREE - open-source models, no credit card)",
        },
        "openai": {
            "available": bool(OPENAI_API_KEY and not OPENAI_API_KEY.startswith("sk-your")),
            "models": ["gpt-4o-mini"],
            "description": "OpenAI API (paid, used as fallback)",
        },
    }
    return {
        "providers": models,
        "active": get_active_model(),
    }


# ── RAG Prompt Template ──────────────────────────────────────────
RAG_PROMPT = PromptTemplate(
    input_variables=["context", "question"],
    template="""You are Easy-Study, an intelligent AI study assistant.
Use ONLY the following context to answer the question accurately.
If the context does not contain enough information, say "I don't have enough information in the provided sources."

Context:
{context}

Question: {question}

Answer:""",
)

FALLBACK_PROMPT = """You are Easy-Study, an intelligent AI study assistant.
Answer the following question as accurately and helpfully as possible:

Question: {question}

Answer:"""


# ── Generation Functions ─────────────────────────────────────────

def _get_ollama_llm(model: Optional[str] = None):
    """Thread-safe singleton Ollama LLM — avoids ~50-100ms client re-creation."""
    model_name = model or OLLAMA_MODEL
    if model_name not in _ollama_llm_cache:
        with _client_lock:
            if model_name not in _ollama_llm_cache:
                from langchain_ollama import OllamaLLM
                _ollama_llm_cache[model_name] = OllamaLLM(
                    model=model_name,
                    base_url=OLLAMA_BASE_URL,
                    temperature=0.1,
                    timeout=30,
                )
    return _ollama_llm_cache[model_name]


def generate_with_ollama(context: str, question: str, model: Optional[str] = None) -> str:
    """Generate answer using local Ollama LLM (singleton client)."""
    try:
        llm = _get_ollama_llm(model)
        prompt = RAG_PROMPT.format(context=context, question=question)
        response = llm.invoke(prompt)
        return str(response).strip()
    except Exception as e:
        raise RuntimeError(f"Ollama LLM error: {e}") from e



def generate_with_gemini(context: str, question: str, model: Optional[str] = None) -> str:
    """Generate answer using Google Gemini API (FREE tier). Uses selected model only."""
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not configured. Get a FREE key at https://aistudio.google.com/apikey")

    client = _get_gemini_client()
    model_id = model or "gemini-2.5-flash"

    if context and context.strip():
        prompt = (
            "You are Easy-Study, an intelligent AI study assistant. "
            "Answer the question using ONLY the provided context.\n\n"
            f"Context:\n{context}\n\nQuestion: {question}\n\nAnswer:"
        )
    else:
        prompt = (
            "You are Easy-Study, a helpful AI study assistant. "
            f"Answer this question accurately:\n\n{question}"
        )

    try:
        response = client.models.generate_content(
            model=model_id,
            contents=prompt,
            config={"temperature": 0.2, "max_output_tokens": 1024},
        )
        return response.text.strip()
    except Exception as e:
        err = str(e)
        if "429" in err or "RESOURCE_EXHAUSTED" in err:
            raise RuntimeError("Rate limit reached. Please wait 1 minute or switch to another model.") from e
        raise RuntimeError(f"Gemini error: {err[:200]}") from e


def generate_with_openrouter(context: str, question: str, model: Optional[str] = None) -> str:
    """Generate answer using OpenRouter (FREE open-source models)."""
    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY not configured. Get a FREE key at https://openrouter.ai")
    try:
        client = _get_openrouter_client()
        model_id = model or "openrouter/free"

        if context and context.strip():
            system_msg = "You are Easy-Study, an intelligent AI study assistant. Answer questions using the provided context."
            user_msg = f"Context:\n{context}\n\nQuestion: {question}\n\nAnswer:"
        else:
            system_msg = "You are Easy-Study, a helpful AI study assistant."
            user_msg = question

        response = client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.2,
            max_tokens=2048,
        )
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("Model returned empty response")
        return content.strip()
    except Exception as e:
        err = str(e)
        if "429" in err:
            raise RuntimeError("Rate limit reached. Please wait and try again or switch model.") from e
        if "404" in err:
            raise RuntimeError("Model not available. Please switch to another model.") from e
        raise RuntimeError(f"OpenRouter error: {err[:200]}") from e


def generate_with_openai(question: str) -> str:
    """Fallback to OpenAI API when local confidence is too low."""
    if not OPENAI_API_KEY or OPENAI_API_KEY.startswith("sk-your"):
        raise ValueError("OpenAI API key not configured")
    try:
        client = _get_openai_client()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are Easy-Study, a helpful AI study assistant."},
                {"role": "user", "content": question},
            ],
            temperature=0.2,
            max_tokens=1024,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        raise RuntimeError(f"OpenAI fallback error: {e}") from e


# ── Module 8: Confidence Checker ─────────────────────────────────
def compute_confidence(results: List[Tuple[Document, float]]) -> float:
    """Compute overall confidence from FAISS similarity scores."""
    if not results:
        return 0.0
    scores = [score for _, score in results]
    if len(scores) == 1:
        return scores[0]
    weighted = (scores[0] * 2 + sum(scores[1:])) / (len(scores) + 1)
    return round(weighted, 4)


def is_confident(results: List[Tuple[Document, float]]) -> bool:
    """Return True if confidence is above the configured threshold."""
    return compute_confidence(results) >= CONFIDENCE_THRESHOLD


def build_context(results: List[Tuple[Document, float]]) -> str:
    """Concatenate retrieved chunks into a single context block."""
    parts = []
    for i, (doc, score) in enumerate(results, 1):
        source = doc.metadata.get("source_name", "unknown")
        src_type = doc.metadata.get("source_type", "?")
        parts.append(
            f"[Source {i} | {src_type} | {source} | score: {score:.3f}]\n"
            + doc.page_content
        )
    return "\n\n".join(parts)


# ── Provider-Aware Generation ────────────────────────────────────
def generate_with_active_model(context: str, question: str) -> str:
    """Generate answer using whichever provider/model is currently active."""
    if _active_provider == "ollama":
        return generate_with_ollama(context, question, _active_model)
    elif _active_provider == "gemini":
        return generate_with_gemini(context, question, _active_model)
    elif _active_provider == "openrouter":
        return generate_with_openrouter(context, question, _active_model)
    elif _active_provider == "openai":
        if not OPENAI_API_KEY or OPENAI_API_KEY.startswith("sk-your"):
            raise ValueError("OpenAI API key not configured.")
        client = _get_openai_client()
        system_msg = "You are Easy-Study, an intelligent AI study assistant."
        user_msg = f"Context:\n{context}\n\nQuestion: {question}\n\nAnswer:" if context else question
        response = client.chat.completions.create(
            model=_active_model or "gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.2,
            max_tokens=2048,
        )
        return response.choices[0].message.content.strip()
    else:
        raise ValueError(f"Unknown provider: {_active_provider}")


def generate_fallback(question: str) -> str:
    """Generate a fallback answer using available free providers."""
    errors = []

    # Try Gemini first (free and high quality)
    if GEMINI_API_KEY:
        try:
            return generate_with_gemini("", question)
        except Exception as e:
            errors.append(f"Gemini: {e}")

    # Try OpenRouter (free open-source models)
    if OPENROUTER_API_KEY:
        try:
            return generate_with_openrouter("", question)
        except Exception as e:
            errors.append(f"OpenRouter: {e}")

    # Try OpenAI
    if OPENAI_API_KEY and not OPENAI_API_KEY.startswith("sk-your"):
        try:
            return generate_with_openai(question)
        except Exception as e:
            errors.append(f"OpenAI: {e}")

    raise RuntimeError(f"All fallback providers failed: {'; '.join(errors) or 'No API keys configured'}")


# ── Unified Query Engine ─────────────────────────────────────────
def _prepare_query_context(
    retrieved_results: List[Tuple[Document, float]],
) -> Tuple[float, bool, str, list]:
    """Shared helper: compute confidence, build context and sources list."""
    confidence = compute_confidence(retrieved_results)
    confident = confidence >= CONFIDENCE_THRESHOLD
    has_context = bool(retrieved_results) and confident

    context = ""
    sources = []
    if has_context:
        context = build_context(retrieved_results)
        sources = [
            {
                "source_type": doc.metadata.get("source_type", "?"),
                "source_name": doc.metadata.get("source_name", "unknown"),
                "score": round(score, 4),
                "chunk_id": doc.metadata.get("chunk_id", 0),
                "preview": doc.page_content[:150] + "...",
            }
            for doc, score in retrieved_results
        ]
    return confidence, has_context, context, sources


def answer_query(
    question: str,
    retrieved_results: List[Tuple[Document, float]],
) -> Dict[str, Any]:
    """
    Full query pipeline — ALWAYS uses the selected model directly.
    1. If documents exist and confidence is high, use RAG context
    2. Otherwise, use the selected model without context (direct chat)
    3. No fallback chain — the selected model is the one that answers
    """
    confidence, has_context, context, sources = _prepare_query_context(retrieved_results)

    # ── Use the SELECTED model directly ────────────────────────
    try:
        answer = generate_with_active_model(context, question)
        return {
            "answer": answer,
            "source": f"{_active_provider}_rag" if has_context else f"{_active_provider}_direct",
            "model": _active_model,
            "provider": _active_provider,
            "confidence": confidence,
            "triggered_fallback": False,
            "retrieved_chunks": len(retrieved_results) if has_context else 0,
            "sources": sources if has_context else None,
        }
    except Exception as err:
        return {
            "answer": f"Error from {_active_provider}/{_active_model}: {err}",
            "source": "error",
            "provider": _active_provider,
            "model": _active_model,
            "confidence": confidence,
            "triggered_fallback": False,
            "retrieved_chunks": 0,
            "reason": str(err),
        }


# ── Streaming Generation (token-by-token) ────────────────────────

def stream_with_ollama(context: str, question: str, model: Optional[str] = None):
    """Yield answer tokens from Ollama."""
    llm = _get_ollama_llm(model)
    prompt = RAG_PROMPT.format(context=context, question=question) if context else FALLBACK_PROMPT.format(question=question)
    for chunk in llm.stream(prompt):
        yield str(chunk)


def stream_with_gemini(context: str, question: str, model: Optional[str] = None):
    """Yield answer tokens from Google Gemini."""
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not configured")
    client = _get_gemini_client()
    model_id = model or "gemini-2.5-flash"
    if context and context.strip():
        prompt = (
            "You are Easy-Study, an intelligent AI study assistant. "
            "Answer the question using ONLY the provided context.\n\n"
            f"Context:\n{context}\n\nQuestion: {question}\n\nAnswer:"
        )
    else:
        prompt = (
            "You are Easy-Study, a helpful AI study assistant. "
            f"Answer this question accurately:\n\n{question}"
        )
    response = client.models.generate_content_stream(
        model=model_id,
        contents=prompt,
        config={"temperature": 0.2, "max_output_tokens": 1024},
    )
    for chunk in response:
        if chunk.text:
            yield chunk.text


def stream_with_openrouter(context: str, question: str, model: Optional[str] = None):
    """Yield answer tokens from OpenRouter."""
    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY not configured")
    client = _get_openrouter_client()
    model_id = model or "openrouter/free"
    if context and context.strip():
        system_msg = "You are Easy-Study, an intelligent AI study assistant. Answer questions using the provided context."
        user_msg = f"Context:\n{context}\n\nQuestion: {question}\n\nAnswer:"
    else:
        system_msg = "You are Easy-Study, a helpful AI study assistant."
        user_msg = question
    response = client.chat.completions.create(
        model=model_id,
        messages=[{"role": "system", "content": system_msg}, {"role": "user", "content": user_msg}],
        temperature=0.2,
        max_tokens=2048,
        stream=True,
    )
    for chunk in response:
        delta = chunk.choices[0].delta if chunk.choices else None
        if delta and delta.content:
            yield delta.content


def stream_with_openai_provider(context: str, question: str, model: Optional[str] = None):
    """Yield answer tokens from OpenAI."""
    if not OPENAI_API_KEY or OPENAI_API_KEY.startswith("sk-your"):
        raise ValueError("OpenAI API key not configured")
    client = _get_openai_client()
    system_msg = "You are Easy-Study, an intelligent AI study assistant."
    user_msg = f"Context:\n{context}\n\nQuestion: {question}\n\nAnswer:" if context else question
    response = client.chat.completions.create(
        model=model or "gpt-4o-mini",
        messages=[{"role": "system", "content": system_msg}, {"role": "user", "content": user_msg}],
        temperature=0.2,
        max_tokens=2048,
        stream=True,
    )
    for chunk in response:
        delta = chunk.choices[0].delta if chunk.choices else None
        if delta and delta.content:
            yield delta.content


def stream_with_active_model(context: str, question: str):
    """Yield tokens from whichever provider/model is currently active."""
    if _active_provider == "ollama":
        yield from stream_with_ollama(context, question, _active_model)
    elif _active_provider == "gemini":
        yield from stream_with_gemini(context, question, _active_model)
    elif _active_provider == "openrouter":
        yield from stream_with_openrouter(context, question, _active_model)
    elif _active_provider == "openai":
        yield from stream_with_openai_provider(context, question, _active_model)
    else:
        raise ValueError(f"Unknown provider: {_active_provider}")


def answer_query_stream(
    question: str,
    retrieved_results: List[Tuple[Document, float]],
):
    """
    Streaming query pipeline — yields metadata dict first, then answer tokens.
    This allows the frontend to display metadata immediately while tokens stream in.
    """
    confidence, has_context, context, sources = _prepare_query_context(retrieved_results)

    # Yield metadata as first item
    meta = {
        "type": "meta",
        "source": f"{_active_provider}_rag" if has_context else f"{_active_provider}_direct",
        "model": _active_model,
        "provider": _active_provider,
        "confidence": confidence,
        "triggered_fallback": False,
        "retrieved_chunks": len(retrieved_results) if has_context else 0,
        "sources": sources if has_context else None,
    }
    yield meta

    # Yield answer tokens
    try:
        for token in stream_with_active_model(context, question):
            yield {"type": "token", "content": token}
        yield {"type": "done"}
    except Exception as err:
        yield {"type": "error", "content": str(err)}
