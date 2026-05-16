"""
Persistent Storage Module – SQLite Database
Stores chat history with conversation management, ingested source metadata.
"""

from __future__ import annotations

import os
import queue
import sqlite3
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from contextlib import contextmanager

from app.utils.logging_config import logger

# ── Database Path ─────────────────────────────────────────────────
DB_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
DB_PATH = os.path.join(DB_DIR, "easystudy.db")

# ── Connection Pool ───────────────────────────────────────────────
# Reuses SQLite connections across calls instead of open/close each time.
# Saves ~5-15ms per DB operation. Pool size=4 is enough for SQLite WAL mode.
_pool: queue.Queue[sqlite3.Connection] = queue.Queue(maxsize=4)
_pool_initialized = False


def _create_connection() -> sqlite3.Connection:
    """Create a new optimized SQLite connection."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")    # Faster writes, still safe with WAL
    conn.execute("PRAGMA cache_size=-8000")       # 8MB page cache
    conn.execute("PRAGMA temp_store=MEMORY")      # Temp tables in RAM
    return conn


@contextmanager
def get_db():
    """Context manager for database connections with connection pooling."""
    try:
        conn = _pool.get_nowait()
    except queue.Empty:
        conn = _create_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        try:
            _pool.put_nowait(conn)
        except queue.Full:
            conn.close()


def init_database() -> None:
    """Create all tables if they don't exist. Safe to call multiple times."""
    with get_db() as conn:
        # Create tables (IF NOT EXISTS won't modify existing ones)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id          TEXT PRIMARY KEY,
                title       TEXT DEFAULT 'New Chat',
                created_at  TEXT DEFAULT (datetime('now', 'localtime')),
                updated_at  TEXT DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS chat_history (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT DEFAULT '',
                question        TEXT NOT NULL,
                answer          TEXT NOT NULL,
                provider        TEXT DEFAULT '',
                model           TEXT DEFAULT '',
                confidence      REAL DEFAULT 0.0,
                source          TEXT DEFAULT 'rag',
                cached          INTEGER DEFAULT 0,
                created_at      TEXT DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS ingested_sources (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                source_name TEXT NOT NULL,
                source_type TEXT NOT NULL,
                chunks      INTEGER DEFAULT 0,
                file_size   INTEGER DEFAULT 0,
                status      TEXT DEFAULT 'active',
                created_at  TEXT DEFAULT (datetime('now', 'localtime'))
            );
        """)

        # Migration: add conversation_id column if missing (existing DBs)
        try:
            conn.execute("SELECT conversation_id FROM chat_history LIMIT 1")
        except sqlite3.OperationalError:
            conn.execute("ALTER TABLE chat_history ADD COLUMN conversation_id TEXT DEFAULT ''")
            conn.commit()

        # Create indexes after migration
        conn.executescript("""
            CREATE INDEX IF NOT EXISTS idx_chat_created ON chat_history(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_chat_conv ON chat_history(conversation_id);
            CREATE INDEX IF NOT EXISTS idx_sources_type ON ingested_sources(source_type);
            CREATE INDEX IF NOT EXISTS idx_conv_updated ON conversations(updated_at DESC);
        """)

    logger.success(f"Database initialized -> {DB_PATH}")


def cleanup_old_conversations(hours: int = 24) -> int:
    """Delete conversations and messages older than N hours. Saves memory."""
    with get_db() as conn:
        # Delete old messages
        conn.execute(
            "DELETE FROM chat_history WHERE created_at < datetime('now', 'localtime', ?)",
            (f"-{hours} hours",),
        )
        # Delete old conversations
        cursor = conn.execute(
            "DELETE FROM conversations WHERE updated_at < datetime('now', 'localtime', ?)",
            (f"-{hours} hours",),
        )
        deleted = cursor.rowcount
        if deleted > 0:
            logger.info(f"Cleaned up {deleted} conversations older than {hours}h")
        return deleted


# ── Conversation Operations ───────────────────────────────────────

def create_conversation(title: str = "New Chat") -> str:
    """Create a new conversation and return its ID."""
    conv_id = str(uuid.uuid4())[:8]
    with get_db() as conn:
        conn.execute(
            "INSERT INTO conversations (id, title) VALUES (?, ?)",
            (conv_id, title),
        )
    return conv_id


def get_conversations(limit: int = 30) -> List[Dict[str, Any]]:
    """List recent conversations, newest first."""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT c.id, c.title, c.created_at, c.updated_at,
                      COUNT(h.id) as message_count
               FROM conversations c
               LEFT JOIN chat_history h ON h.conversation_id = c.id
               GROUP BY c.id
               ORDER BY c.updated_at DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]


def get_conversation_messages(conv_id: str) -> List[Dict[str, Any]]:
    """Get all messages for a conversation, oldest first."""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT id, question, answer, provider, model,
                      confidence, source, cached, created_at
               FROM chat_history
               WHERE conversation_id = ?
               ORDER BY created_at ASC""",
            (conv_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def delete_conversation(conv_id: str) -> bool:
    """Delete a conversation and its messages."""
    with get_db() as conn:
        conn.execute("DELETE FROM chat_history WHERE conversation_id = ?", (conv_id,))
        cursor = conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
        return cursor.rowcount > 0


def update_conversation_title(conv_id: str, title: str) -> None:
    """Update conversation title."""
    with get_db() as conn:
        conn.execute("UPDATE conversations SET title = ? WHERE id = ?", (title, conv_id))


def _update_conversation_timestamp(conn, conv_id: str) -> None:
    """Update the conversation's updated_at timestamp."""
    conn.execute(
        "UPDATE conversations SET updated_at = datetime('now', 'localtime') WHERE id = ?",
        (conv_id,),
    )


# ── Chat History Operations ───────────────────────────────────────

def save_chat_message(
    question: str,
    answer: str,
    provider: str = "",
    model: str = "",
    confidence: float = 0.0,
    source: str = "rag",
    cached: bool = False,
    conversation_id: str = "",
) -> int:
    """Save a chat Q&A pair and return its ID."""
    with get_db() as conn:
        cursor = conn.execute(
            """INSERT INTO chat_history
               (conversation_id, question, answer, provider, model, confidence, source, cached)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (conversation_id, question, answer, provider, model, confidence, source, int(cached)),
        )
        # Auto-set conversation title from first question
        if conversation_id:
            _update_conversation_timestamp(conn, conversation_id)
            # Set title to first question (truncated)
            existing = conn.execute(
                "SELECT title FROM conversations WHERE id = ?", (conversation_id,)
            ).fetchone()
            if existing and existing["title"] == "New Chat":
                title = question[:50] + ("..." if len(question) > 50 else "")
                conn.execute(
                    "UPDATE conversations SET title = ? WHERE id = ?",
                    (title, conversation_id),
                )
        return cursor.lastrowid


def get_chat_history(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """Retrieve recent chat messages, newest first."""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT id, conversation_id, question, answer, provider, model,
                      confidence, source, cached, created_at
               FROM chat_history
               ORDER BY created_at DESC
               LIMIT ? OFFSET ?""",
            (limit, offset),
        ).fetchall()
        return [dict(row) for row in rows]


def get_chat_stats() -> Dict[str, Any]:
    """Return chat statistics."""
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM chat_history").fetchone()[0]
        cached = conn.execute(
            "SELECT COUNT(*) FROM chat_history WHERE cached = 1"
        ).fetchone()[0]
        providers = conn.execute(
            """SELECT provider, COUNT(*) as count
               FROM chat_history GROUP BY provider"""
        ).fetchall()
        return {
            "total_messages": total,
            "cached_responses": cached,
            "by_provider": {row["provider"]: row["count"] for row in providers},
        }


def clear_chat_history() -> int:
    """Delete all chat history and conversations. Returns number of deleted rows."""
    with get_db() as conn:
        cursor = conn.execute("DELETE FROM chat_history")
        conn.execute("DELETE FROM conversations")
        return cursor.rowcount


# ── Ingested Source Operations ────────────────────────────────────

def save_ingested_source(
    source_name: str,
    source_type: str,
    chunks: int = 0,
    file_size: int = 0,
) -> int:
    """Record an ingested document source. Returns its ID."""
    with get_db() as conn:
        cursor = conn.execute(
            """INSERT INTO ingested_sources
               (source_name, source_type, chunks, file_size)
               VALUES (?, ?, ?, ?)""",
            (source_name, source_type, chunks, file_size),
        )
        return cursor.lastrowid


def get_ingested_sources() -> List[Dict[str, Any]]:
    """List all ingested sources, newest first."""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT id, source_name, source_type, chunks,
                      file_size, status, created_at
               FROM ingested_sources
               ORDER BY created_at DESC"""
        ).fetchall()
        return [dict(row) for row in rows]


def get_source_stats() -> Dict[str, Any]:
    """Return ingested source statistics."""
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM ingested_sources").fetchone()[0]
        total_chunks = conn.execute(
            "SELECT COALESCE(SUM(chunks), 0) FROM ingested_sources"
        ).fetchone()[0]
        by_type = conn.execute(
            """SELECT source_type, COUNT(*) as count, SUM(chunks) as total_chunks
               FROM ingested_sources GROUP BY source_type"""
        ).fetchall()
        return {
            "total_sources": total,
            "total_chunks": total_chunks,
            "by_type": {
                row["source_type"]: {"count": row["count"], "chunks": row["total_chunks"]}
                for row in by_type
            },
        }


def delete_source(source_id: int) -> bool:
    """Soft-delete a source by marking it inactive."""
    with get_db() as conn:
        cursor = conn.execute(
            "UPDATE ingested_sources SET status = 'deleted' WHERE id = ?",
            (source_id,),
        )
        return cursor.rowcount > 0
