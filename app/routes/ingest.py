"""
API Routes: /api/upload  (for PDF & text)
           /api/ingest   (for URL / YouTube)
Rate-limited and with persistent source tracking in SQLite.
Blocking operations wrapped in asyncio.to_thread.
File upload validation for size and type security.
"""

from __future__ import annotations

import asyncio
from fastapi import APIRouter, File, UploadFile, Form, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings
from app.schemas import URLIngestRequest, TextIngestRequest
from app.modules.ingestion import ingest_source, detect_input_type
from app.modules.vector_store import process_and_store
from app.modules.database import save_ingested_source

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()

# ── Security: allowed MIME types for upload ──────────────────────
ALLOWED_PDF_TYPES = {
    "application/pdf",
    "application/x-pdf",
}
ALLOWED_TEXT_TYPES = {
    "text/plain",
    "application/octet-stream",  # some browsers send .txt as this
}


# ── POST /api/upload  (PDF or text file) ─────────────────────────
@router.post("/upload")
@limiter.limit("20/minute")
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    source_type: str = Form("pdf"),
):
    """
    Upload a PDF or text file for ingestion into the vector store.
    - **file**: The file to upload (PDF or .txt)
    - **source_type**: 'pdf' or 'text'
    """
    allowed_types = {"pdf", "text"}
    if source_type not in allowed_types:
        raise HTTPException(400, f"source_type must be one of {allowed_types}")

    # ── Security: validate MIME type ──────────────────────────────
    content_type = (file.content_type or "").lower()
    if source_type == "pdf" and content_type not in ALLOWED_PDF_TYPES:
        if not (file.filename or "").lower().endswith(".pdf"):
            raise HTTPException(400, "Invalid file type. Please upload a PDF file.")
    if source_type == "text" and content_type not in ALLOWED_TEXT_TYPES:
        if not (file.filename or "").lower().endswith(".txt"):
            raise HTTPException(400, "Invalid file type. Please upload a text file.")

    try:
        file_bytes = await file.read()

        # ── Security: validate file size ──────────────────────────
        max_bytes = settings.max_upload_size_mb * 1024 * 1024
        if len(file_bytes) > max_bytes:
            raise HTTPException(
                413,
                f"File too large. Maximum allowed: {settings.max_upload_size_mb}MB",
            )

        if source_type == "pdf":
            documents = await asyncio.to_thread(
                ingest_source,
                source_type="pdf",
                file_bytes=file_bytes,
                filename=file.filename,
            )
        else:
            text_content = file_bytes.decode("utf-8", errors="replace")
            documents = await asyncio.to_thread(
                ingest_source,
                source_type="text",
                text=text_content,
                filename=file.filename,
            )

        result = await asyncio.to_thread(process_and_store, documents)

        # Track in SQLite (fast, keep on event loop via thread)
        await asyncio.to_thread(
            save_ingested_source,
            source_name=file.filename or "upload",
            source_type=source_type,
            chunks=result.get("chunks_created", 0),
            file_size=len(file_bytes),
        )

        return {
            "status": "success",
            "message": f"✅ {file.filename} ingested successfully",
            **result,
        }

    except HTTPException:
        raise  # Re-raise HTTP exceptions (like 413) as-is
    except Exception as e:
        raise HTTPException(500, f"Ingestion failed: {e}")


# ── POST /api/ingest  (URL or YouTube) ───────────────────────────
@router.post("/ingest/url")
@limiter.limit("20/minute")
async def ingest_url(request: Request, payload: URLIngestRequest):
    """
    Ingest content from a web article URL or YouTube video link.
    - **url**: The URL to process
    - **source_type**: 'url' or 'youtube' (auto-detected if omitted)
    """
    url = payload.url.strip()
    source_type = payload.source_type or detect_input_type(url)

    if source_type not in {"url", "youtube"}:
        raise HTTPException(400, "URL must be a web article or YouTube link")

    try:
        documents = await asyncio.to_thread(
            ingest_source, source_type=source_type, url=url
        )
        result = await asyncio.to_thread(process_and_store, documents)

        # Track in SQLite
        await asyncio.to_thread(
            save_ingested_source,
            source_name=url,
            source_type=source_type,
            chunks=result.get("chunks_created", 0),
        )

        return {
            "status": "success",
            "message": f"✅ {source_type.upper()} ingested: {url}",
            "detected_type": source_type,
            **result,
        }
    except Exception as e:
        raise HTTPException(500, f"URL ingestion failed: {e}")


# ── POST /api/ingest/text  (raw notes) ───────────────────────────
@router.post("/ingest/text")
@limiter.limit("20/minute")
async def ingest_text(request: Request, payload: TextIngestRequest):
    """
    Ingest raw text / notes directly into the knowledge base.
    - **text**: The content to ingest
    - **title**: Optional label for this note block
    """
    if not payload.text.strip():
        raise HTTPException(400, "text cannot be empty")

    try:
        documents = await asyncio.to_thread(
            ingest_source,
            source_type="text",
            text=payload.text,
            filename=payload.title,
        )
        result = await asyncio.to_thread(process_and_store, documents)

        # Track in SQLite
        await asyncio.to_thread(
            save_ingested_source,
            source_name=payload.title or "User Notes",
            source_type="text",
            chunks=result.get("chunks_created", 0),
            file_size=len(payload.text.encode("utf-8")),
        )

        return {
            "status": "success",
            "message": f"✅ Text notes ingested: '{payload.title}'",
            **result,
        }
    except Exception as e:
        raise HTTPException(500, f"Text ingestion failed: {e}")
