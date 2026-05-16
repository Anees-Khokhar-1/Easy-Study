@echo off
echo.
echo  ====================================================
echo   Easy-Study RAG System - Startup
echo  ====================================================
echo.

:: ── Pre-flight checks ──────────────────────────────────────
where python >nul 2>&1 || (
    echo [ERROR] Python is not installed or not in PATH.
    echo         Download from https://python.org
    pause
    exit /b 1
)

:: ── Check .env ─────────────────────────────────────────────
if not exist ".env" (
    echo [SETUP] Creating .env from .env.example...
    copy .env.example .env >nul
    echo         Please edit .env and set your OPENAI_API_KEY
    echo.
)

:: ── Check virtual environment ──────────────────────────────
if not exist "venv" (
    echo [1/3] Creating virtual environment...
    python -m venv venv
)

:: ── Activate virtual environment ───────────────────────────
echo [2/3] Activating virtual environment...
call venv\Scripts\activate.bat

:: ── Install dependencies ───────────────────────────────────
echo [3/3] Installing dependencies (first run may take a few minutes)...
pip install -r requirements.txt --quiet

:: ── Create data directories ────────────────────────────────
if not exist "data\faiss_index" mkdir data\faiss_index
if not exist "data\uploads"    mkdir data\uploads
if not exist "data\logs"       mkdir data\logs

:: ── Start server ───────────────────────────────────────────
echo.
echo  ====================================================
echo   Server:   http://localhost:8000
echo   Swagger:  http://localhost:8000/docs
echo   Press Ctrl+C to stop
echo  ====================================================
echo.

python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
