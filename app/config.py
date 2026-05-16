"""
Centralized Application Configuration – Pydantic Settings
Single source of truth for all config values, loaded from .env.
Import `settings` from this module instead of calling os.getenv() everywhere.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from .env file."""

    # ── OpenAI Fallback API ──────────────────────────────────────
    openai_api_key: str = ""

    # ── Google Gemini API (FREE) ─────────────────────────────────
    gemini_api_key: str = ""

    # ── OpenRouter API (FREE) ────────────────────────────────────
    openrouter_api_key: str = ""

    # ── Ollama Configuration ─────────────────────────────────────
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"

    # ── Embedding Model ──────────────────────────────────────────
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # ── RAG Configuration ────────────────────────────────────────
    chunk_size: int = 1000
    chunk_overlap: int = 200
    top_k_results: int = 5
    confidence_threshold: float = 0.50

    # ── FAISS Index Path ─────────────────────────────────────────
    faiss_index_path: str = "./data/faiss_index"

    # ── Server Config ────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8000

    # ── Security Config ──────────────────────────────────────────
    max_upload_size_mb: int = 50
    debug: bool = False

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Ignore extra env vars


# ── Singleton instance ───────────────────────────────────────────
settings = Settings()
