"""
Response Cache Module – In-Memory LRU Cache with Semantic Similarity
Caches query results with two-tier lookup:
  1. Exact hash match (instant — O(1))
  2. Semantic similarity via embedding cosine distance (fast — ~5ms)
Avoids redundant LLM calls for identical AND rephrased questions.
"""

from __future__ import annotations

import hashlib
import threading
import time
from collections import OrderedDict
from typing import Any, Optional, List, Dict

import numpy as np

from app.utils.logging_config import logger


# ── Embedding Cache (avoids re-embedding the same query text) ─────
_embed_cache: Dict[str, np.ndarray] = {}
_embed_cache_lock = threading.Lock()
_MAX_EMBED_CACHE = 500


def _get_query_embedding(question: str) -> Optional[np.ndarray]:
    """Get embedding for a question, using a local cache to avoid re-encoding."""
    key = question.strip().lower()
    with _embed_cache_lock:
        if key in _embed_cache:
            return _embed_cache[key]

    try:
        from app.modules.vector_store import get_embeddings
        emb_model = get_embeddings()
        vector = np.array(emb_model.embed_query(key), dtype=np.float32)
        # Normalize for cosine similarity via dot product
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm
        with _embed_cache_lock:
            if len(_embed_cache) >= _MAX_EMBED_CACHE:
                # Evict oldest (first inserted)
                oldest_key = next(iter(_embed_cache))
                del _embed_cache[oldest_key]
            _embed_cache[key] = vector
        return vector
    except Exception:
        return None


class LRUCache:
    """Thread-safe LRU cache with TTL and semantic similarity lookup."""

    def __init__(
        self,
        max_size: int = 100,
        ttl_seconds: int = 3600,
        similarity_threshold: float = 0.92,
    ):
        self._cache: OrderedDict[str, dict] = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._similarity_threshold = similarity_threshold
        self._hits = 0
        self._semantic_hits = 0
        self._misses = 0
        self._lock = threading.Lock()

    def _make_key(self, question: str, top_k: int, model: str) -> str:
        """Generate a unique cache key from query parameters."""
        raw = f"{question.strip().lower()}|{top_k}|{model}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def get(self, question: str, top_k: int, model: str) -> Optional[dict]:
        """
        Retrieve cached result using two-tier lookup:
        1. Exact hash match (instant)
        2. Semantic similarity over cached embeddings (~5ms)
        """
        key = self._make_key(question, top_k, model)
        now = time.time()

        with self._lock:
            # ── Tier 1: Exact match ─────────────────────────────
            if key in self._cache:
                entry = self._cache[key]
                if now - entry["timestamp"] > self._ttl:
                    del self._cache[key]
                else:
                    self._cache.move_to_end(key)
                    self._hits += 1
                    logger.debug(f"Cache EXACT HIT: {question[:50]}…")
                    return entry["data"].copy()

        # ── Tier 2: Semantic similarity (outside lock — embedding is slow) ──
        query_vec = _get_query_embedding(question)
        if query_vec is not None:
            best_match = None
            best_score = 0.0

            with self._lock:
                for cached_key, entry in self._cache.items():
                    if now - entry["timestamp"] > self._ttl:
                        continue
                    # Only match same model
                    if entry.get("model") != model:
                        continue
                    cached_vec = entry.get("embedding")
                    if cached_vec is None:
                        continue
                    score = float(np.dot(query_vec, cached_vec))
                    if score > best_score:
                        best_score = score
                        best_match = cached_key

                if best_match and best_score >= self._similarity_threshold:
                    entry = self._cache[best_match]
                    self._cache.move_to_end(best_match)
                    self._semantic_hits += 1
                    logger.debug(
                        f"Cache SEMANTIC HIT (score={best_score:.3f}): {question[:50]}…"
                    )
                    return entry["data"].copy()

        with self._lock:
            self._misses += 1
        return None

    def put(
        self, question: str, top_k: int, model: str, data: dict
    ) -> None:
        """Store a result in the cache with its embedding for semantic lookup."""
        key = self._make_key(question, top_k, model)
        embedding = _get_query_embedding(question)

        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                self._cache[key] = {
                    "data": data,
                    "timestamp": time.time(),
                    "model": model,
                    "embedding": embedding,
                }
                return

            if len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)  # Remove oldest

            self._cache[key] = {
                "data": data,
                "timestamp": time.time(),
                "model": model,
                "embedding": embedding,
            }

    def clear(self) -> None:
        """Clear all cached entries."""
        with self._lock:
            self._cache.clear()
        with _embed_cache_lock:
            _embed_cache.clear()
        logger.info("Response cache cleared")

    def stats(self) -> dict:
        """Return cache statistics."""
        with self._lock:
            total = self._hits + self._semantic_hits + self._misses
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "exact_hits": self._hits,
                "semantic_hits": self._semantic_hits,
                "total_hits": self._hits + self._semantic_hits,
                "misses": self._misses,
                "hit_rate": (
                    f"{((self._hits + self._semantic_hits) / total * 100):.1f}%"
                    if total > 0
                    else "0%"
                ),
                "ttl_seconds": self._ttl,
                "similarity_threshold": self._similarity_threshold,
            }


# ── Singleton cache instance ─────────────────────────────────────
query_cache = LRUCache(max_size=200, ttl_seconds=1800, similarity_threshold=0.92)
