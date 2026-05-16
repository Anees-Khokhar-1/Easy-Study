"""
Study Tools Module – AI-powered Flashcards, Quizzes & Summaries
Uses the existing RAG pipeline (FAISS retrieval + LLM) to generate
structured study materials from the user's ingested knowledge base.
"""

from __future__ import annotations

import json
import os
import re
from typing import List, Dict, Any, Optional

from app.utils.logging_config import logger
from app.modules.vector_store import retrieve_relevant_chunks
from app.modules.llm_engine import (
    generate_with_active_model,
    build_context,
    compute_confidence,
    CONFIDENCE_THRESHOLD,
    OLLAMA_MODEL,
)


# ── Prompt Templates ──────────────────────────────────────────────

FLASHCARD_PROMPT = """You are Easy-Study, an expert study assistant.
Based on the following study material, generate exactly {count} flashcards as a JSON array.
Each flashcard must have:
- "front": a clear question or key term (concise)
- "back": the answer or definition (detailed but focused)
- "difficulty": a number 1-5 (1=easy, 5=hard)

{topic_instruction}

Study Material:
{context}

IMPORTANT: Return ONLY a valid JSON array, no extra text. Example format:
[{{"front":"What is X?","back":"X is...","difficulty":2}}]

Generate {count} flashcards now:"""

QUIZ_PROMPT = """You are Easy-Study, an expert study assistant.
Based on the following study material, generate exactly {count} multiple-choice quiz questions as a JSON array.
Each question must have:
- "question": the question text
- "options": an array of exactly 4 answer choices
- "correct": the index (0-3) of the correct answer
- "explanation": a brief explanation of why the answer is correct

{topic_instruction}

Study Material:
{context}

IMPORTANT: Return ONLY a valid JSON array, no extra text. Example format:
[{{"question":"What is...?","options":["A","B","C","D"],"correct":0,"explanation":"Because..."}}]

Generate {count} quiz questions now:"""

SUMMARY_PROMPT = """You are Easy-Study, an expert study assistant.
Based on the following study material, generate a {length} summary.

{topic_instruction}

Study Material:
{context}

Provide your response as a JSON object with:
- "summary": the full summary text (use markdown formatting)
- "key_points": an array of 3-7 key takeaway bullet points

IMPORTANT: Return ONLY valid JSON, no extra text.
{{"summary":"...","key_points":["...","..."]}}

Generate the summary now:"""


# ── JSON Extraction Helper ────────────────────────────────────────

def _extract_json(text: str) -> Any:
    """
    Robustly extract JSON from LLM output that may contain
    markdown fences, preamble text, or trailing content.
    """
    # Try direct parse first
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strip markdown code fences
    fenced = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Find first [ or { and match to last ] or }
    for start_char, end_char in [("[", "]"), ("{", "}")]:
        start = text.find(start_char)
        end = text.rfind(end_char)
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                continue

    raise ValueError(f"Could not extract valid JSON from LLM response: {text[:200]}…")


# ── LLM Call with Fallback ────────────────────────────────────────

def _call_llm(prompt: str) -> str:
    """Use the selected/active model directly — no fallback chain."""
    return generate_with_active_model("", prompt)


# ── Retrieve Context for Topic ────────────────────────────────────

def _get_topic_context(topic: Optional[str], top_k: int = 10) -> str:
    """Retrieve relevant chunks for a topic, or get general context."""
    query = topic or "main concepts and key information"
    results = retrieve_relevant_chunks(query, top_k=top_k)
    if not results:
        raise ValueError(
            "No content in knowledge base. Please ingest some study materials first."
        )
    return build_context(results)


# ── Generate Flashcards ───────────────────────────────────────────

def generate_flashcards(
    topic: Optional[str] = None,
    count: int = 10,
) -> Dict[str, Any]:
    """
    Generate flashcards from the knowledge base.
    Returns dict with flashcards array and metadata.
    """
    count = max(1, min(count, 30))  # clamp 1-30

    context = _get_topic_context(topic, top_k=min(count * 2, 15))
    topic_instruction = (
        f'Focus on the topic: "{topic}"' if topic else "Cover the most important concepts."
    )

    prompt = FLASHCARD_PROMPT.format(
        count=count, topic_instruction=topic_instruction, context=context
    )

    logger.info(f"Generating {count} flashcards (topic: {topic or 'general'})")
    raw = _call_llm(prompt)
    flashcards = _extract_json(raw)

    if not isinstance(flashcards, list):
        raise ValueError("LLM did not return a flashcard array")

    # Validate and clean
    cleaned = []
    for i, card in enumerate(flashcards[:count]):
        cleaned.append({
            "id": i,
            "front": str(card.get("front", "")).strip(),
            "back": str(card.get("back", "")).strip(),
            "difficulty": max(1, min(5, int(card.get("difficulty", 3)))),
        })

    logger.success(f"Generated {len(cleaned)} flashcards")
    return {
        "flashcards": cleaned,
        "count": len(cleaned),
        "topic": topic or "General",
        "source": "knowledge_base",
    }


# ── Generate Quiz ─────────────────────────────────────────────────

def generate_quiz(
    topic: Optional[str] = None,
    count: int = 5,
) -> Dict[str, Any]:
    """
    Generate a multiple-choice quiz from the knowledge base.
    Returns dict with questions array and metadata.
    """
    count = max(1, min(count, 20))  # clamp 1-20

    context = _get_topic_context(topic, top_k=min(count * 3, 15))
    topic_instruction = (
        f'Focus on the topic: "{topic}"' if topic else "Cover the most important concepts."
    )

    prompt = QUIZ_PROMPT.format(
        count=count, topic_instruction=topic_instruction, context=context
    )

    logger.info(f"Generating {count} quiz questions (topic: {topic or 'general'})")
    raw = _call_llm(prompt)
    questions = _extract_json(raw)

    if not isinstance(questions, list):
        raise ValueError("LLM did not return a quiz array")

    # Validate and clean
    cleaned = []
    for i, q in enumerate(questions[:count]):
        options = q.get("options", [])
        if len(options) < 4:
            options = (options + ["N/A"] * 4)[:4]
        cleaned.append({
            "id": i,
            "question": str(q.get("question", "")).strip(),
            "options": [str(o).strip() for o in options[:4]],
            "correct": max(0, min(3, int(q.get("correct", 0)))),
            "explanation": str(q.get("explanation", "")).strip(),
        })

    logger.success(f"Generated {len(cleaned)} quiz questions")
    return {
        "questions": cleaned,
        "count": len(cleaned),
        "topic": topic or "General",
        "source": "knowledge_base",
    }


# ── Generate Summary ──────────────────────────────────────────────

def generate_summary(
    topic: Optional[str] = None,
    length: str = "medium",
) -> Dict[str, Any]:
    """
    Generate a summary of the ingested content.
    Length: short (~100 words), medium (~250 words), long (~500 words).
    """
    length = length if length in ("short", "medium", "long") else "medium"

    context = _get_topic_context(topic, top_k=10)
    topic_instruction = (
        f'Focus on the topic: "{topic}"' if topic else "Cover all major concepts."
    )

    prompt = SUMMARY_PROMPT.format(
        length=length, topic_instruction=topic_instruction, context=context
    )

    logger.info(f"Generating {length} summary (topic: {topic or 'general'})")
    raw = _call_llm(prompt)
    result = _extract_json(raw)

    if not isinstance(result, dict):
        raise ValueError("LLM did not return a summary object")

    summary = {
        "summary": str(result.get("summary", "")).strip(),
        "key_points": [str(kp).strip() for kp in result.get("key_points", [])],
        "length": length,
        "topic": topic or "General",
        "source": "knowledge_base",
    }

    logger.success(f"Generated {length} summary with {len(summary['key_points'])} key points")
    return summary
