"""
Easy-Study RAG System – FastAPI Entry Point
v2.0 — With database init, rate limiting, and history routes.
Security hardened with headers, GZip, request size limits, and error sanitization.
"""

import os
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from dotenv import load_dotenv
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

import threading
from app.config import settings
from app.utils.logging_config import logger
from app.modules.database import init_database, cleanup_old_conversations

from app.routes.ingest import router as ingest_router
from app.routes.query import router as query_router
from app.routes.health import router as health_router
from app.routes.generate import router as generate_router
from app.routes.models import router as models_router
from app.routes.history import router as history_router

load_dotenv()

# ── Rate Limiter ──────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])


# ── Lifespan: startup / shutdown ─────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs("./data/faiss_index", exist_ok=True)
    os.makedirs("./data/uploads", exist_ok=True)
    os.makedirs("./data/logs", exist_ok=True)
    init_database()
    cleanup_old_conversations(hours=24)
    # Preload embedding model in background so first query is fast
    def _preload():
        try:
            from app.modules.vector_store import get_embeddings
            get_embeddings()
            logger.success("Embedding model preloaded in background")
        except Exception:
            pass
    threading.Thread(target=_preload, daemon=True).start()
    logger.info("Easy-Study RAG System started")
    yield
    logger.info("Easy-Study RAG System shutting down")


# ── App Factory ───────────────────────────────────────────────────
app = FastAPI(
    title="Easy-Study RAG System",
    description="Multi-Source Retrieval-Augmented Generation with Smart Fallback AI",
    version="2.0.0",
    lifespan=lifespan,
)

# ── Middleware Stack (order matters: last added = first executed) ──

# 1. GZip compression — compress responses > 1KB for faster transfer
app.add_middleware(GZipMiddleware, minimum_size=1000)

# 2. Attach rate limiter to the app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 3. CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:3000",  # dev frontend if using separate server
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Security: Headers Middleware ──────────────────────────────────
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to all responses to prevent common attacks."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=(), payment=()"
    )
    # Cache-Control for API responses (no caching sensitive data)
    # Exclude streaming endpoint — SSE needs to flow without cache interference
    if request.url.path.startswith("/api/") and not request.url.path.endswith("/stream"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
    return response


# ── Security: Request Size Limit Middleware ───────────────────────
@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    """Reject oversized request bodies to prevent DoS attacks."""
    content_length = request.headers.get("content-length")
    if content_length:
        max_bytes = settings.max_upload_size_mb * 1024 * 1024
        if int(content_length) > max_bytes:
            return JSONResponse(
                status_code=413,
                content={
                    "detail": f"Request body too large. Maximum: {settings.max_upload_size_mb}MB"
                },
            )
    return await call_next(request)


# ── Security: Global Exception Handler ────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Catch unhandled exceptions and return sanitized error messages.
    In production (debug=False), internal details are hidden from the client.
    """
    if settings.debug:
        detail = f"Internal server error: {exc}"
    else:
        detail = "An internal error occurred. Please try again later."
    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}")
    return JSONResponse(status_code=500, content={"detail": detail})


# ── API Routers ───────────────────────────────────────────────────
app.include_router(health_router, prefix="/api", tags=["health"])
app.include_router(ingest_router, prefix="/api", tags=["ingest"])
app.include_router(query_router, prefix="/api", tags=["query"])
app.include_router(generate_router, prefix="/api", tags=["study-tools"])
app.include_router(models_router, prefix="/api", tags=["models"])
app.include_router(history_router, prefix="/api", tags=["history"])

# ── Serve Frontend ────────────────────────────────────────────────
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
static_dir = os.path.join(frontend_dir, "static")

if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", include_in_schema=False)
async def serve_frontend():
    index_path = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Easy-Study RAG API is running. Visit /docs for API reference."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        reload=True,
    )
