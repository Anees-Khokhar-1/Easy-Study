"""
Module 1 + 2: Input Handler & Data Ingestion
Detects input type and loads/extracts content from PDF, URL, YouTube, or plain text.
"""

from __future__ import annotations

import re
import tempfile
import os
from pathlib import Path
from typing import List

from langchain.schema import Document


# ── YouTube URL detection ─────────────────────────────────────────
_YT_PATTERN = re.compile(
    r"(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/)[\w\-]+"
)


def detect_input_type(source: str) -> str:
    """Return one of: 'pdf', 'youtube', 'url', 'text'."""
    if source.lower().endswith(".pdf") or source.startswith("data:application/pdf"):
        return "pdf"
    if _YT_PATTERN.match(source):
        return "youtube"
    if source.startswith("http://") or source.startswith("https://"):
        return "url"
    return "text"


# ── PDF Loader ────────────────────────────────────────────────────
def load_pdf(file_bytes: bytes, filename: str = "upload.pdf") -> List[Document]:
    from langchain_community.document_loaders import PyPDFLoader

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        loader = PyPDFLoader(tmp_path)
        docs = loader.load()
        for doc in docs:
            doc.metadata["source_type"] = "pdf"
            doc.metadata["source_name"] = filename
        return docs
    finally:
        os.unlink(tmp_path)


# ── URL / Article Loader ─────────────────────────────────────────
def load_url(url: str) -> List[Document]:
    from langchain_community.document_loaders import WebBaseLoader

    loader = WebBaseLoader(url)
    docs = loader.load()
    for doc in docs:
        doc.metadata["source_type"] = "url"
        doc.metadata["source_name"] = url
    return docs


# ── YouTube Transcript Loader ─────────────────────────────────────
def load_youtube(url: str) -> List[Document]:
    from youtube_transcript_api import YouTubeTranscriptApi

    # Extract video ID from various YouTube URL formats
    match = re.search(r"(?:v=|youtu\.be/)([\w\-]{11})", url)
    if not match:
        raise ValueError(f"Cannot extract video ID from URL: {url}")
    video_id = match.group(1)

    try:
        # youtube-transcript-api v1.x: instance-based API
        ytt = YouTubeTranscriptApi()
        transcript = ytt.fetch(video_id)
        full_text = " ".join(
            snippet.text for snippet in transcript
        )
    except Exception as e:
        raise ValueError(f"Transcript not available for {url}: {e}")

    doc = Document(
        page_content=full_text,
        metadata={
            "source_type": "youtube",
            "source_name": url,
            "video_id": video_id,
        },
    )
    return [doc]


# ── Plain Text Loader ─────────────────────────────────────────────
def load_text(text: str, source_name: str = "user_notes") -> List[Document]:
    doc = Document(
        page_content=text,
        metadata={
            "source_type": "text",
            "source_name": source_name,
        },
    )
    return [doc]


# ── Unified Ingestion Entry Point ─────────────────────────────────
def ingest_source(
    *,
    source_type: str,
    file_bytes: bytes | None = None,
    filename: str | None = None,
    url: str | None = None,
    text: str | None = None,
) -> List[Document]:
    """
    Dispatch to the correct loader based on source_type.
    Returns a list of LangChain Documents.
    """
    if source_type == "pdf":
        if not file_bytes:
            raise ValueError("file_bytes required for PDF ingestion")
        return load_pdf(file_bytes, filename or "upload.pdf")
    elif source_type == "url":
        if not url:
            raise ValueError("url required for URL ingestion")
        return load_url(url)
    elif source_type == "youtube":
        if not url:
            raise ValueError("url required for YouTube ingestion")
        return load_youtube(url)
    elif source_type == "text":
        if not text:
            raise ValueError("text required for text ingestion")
        return load_text(text, filename or "user_notes")
    else:
        raise ValueError(f"Unknown source_type: {source_type}")
