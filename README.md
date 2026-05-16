# 📚 Easy-Study — AI-Powered Multi-Model Study Assistant

[![Python CI/CD Pipeline](https://github.com/Anees-Khokhar-1/Easy-Study/actions/workflows/python-ci.yml/badge.svg)](https://github.com/Anees-Khokhar-1/Easy-Study/actions/workflows/python-ci.yml)

> **Ingest · Retrieve · Learn** — Upload your study materials, switch between AI models, and get intelligent answers powered by RAG.

A production-ready, modular RAG (Retrieval-Augmented Generation) platform that:

- Ingests **PDFs**, **web articles**, **YouTube videos**, and **plain text notes**
- Stores them in a **FAISS** vector database using HuggingFace embeddings
- Answers queries via **multiple AI providers** — switch at runtime:
  - ✨ **Gemini** (free cloud) — Gemini 2.5 Flash, 2.0 Flash, 2.0 Flash Lite
  - 🌐 **OpenRouter** (free) — Llama 3.3 70B, DeepSeek R1, Gemma 3, Mistral Small
  - 🖥️ **Ollama** (local) — `llama3:latest`, `llama3.1:8b`
  - 💎 **OpenAI** (paid) — GPT-4o Mini
- Generates **flashcards**, **quizzes**, and **summaries** from your knowledge base
- Features a calming **deep navy + blue/teal** dark UI designed for long study sessions

---

## 🖼️ Features

| Feature | Description |
| ------- | ----------- |
| 💬 **AI Chat** | Ask questions — answers use RAG context from your uploaded materials |
| 🔄 **Multi-Model Switching** | Switch between Gemini, OpenRouter, Ollama, and OpenAI with one click |
| 📄 **PDF Ingestion** | Upload and process multi-page PDF documents |
| 🌐 **URL Ingestion** | Scrape and index web articles |
| 🎬 **YouTube Ingestion** | Extract and index video transcripts |
| 📝 **Notes** | Paste raw text/notes directly into the knowledge base |
| 🃏 **Flashcards** | AI-generated flashcards with difficulty ratings |
| 🧠 **Quizzes** | Multiple-choice quizzes with explanations |
| 📋 **Summaries** | Short/medium/long summaries with key points |
| ⏱️ **Pomodoro Timer** | Built-in study timer with focus/break sessions |
| 🎨 **Education UI** | Deep navy + blue/green palette designed for focus & reduced eye strain |

---

## 🗂️ Project Structure

```text
easy-study/
├── app/                            # ← Active application (run from here)
│   ├── main.py                     # FastAPI entry point + frontend serving
│   ├── config.py                   # Centralized config (Pydantic Settings)
│   ├── schemas.py                  # Request/response Pydantic models
│   ├── modules/
│   │   ├── ingestion.py            # Module 1-2: Input handler & data loaders
│   │   ├── vector_store.py         # Module 3-6: Chunking, embedding, FAISS + cache
│   │   ├── llm_engine.py          # Module 7-9: Multi-provider LLM engine
│   │   ├── study_tools.py         # Flashcard, quiz & summary generation
│   │   └── cache.py               # LRU response cache (query deduplication)
│   ├── routes/
│   │   ├── ingest.py              # POST /api/upload, /api/ingest/url, /api/ingest/text
│   │   ├── query.py               # POST /api/query (with caching)
│   │   ├── models.py             # GET /api/models, POST /api/models/switch
│   │   ├── generate.py           # POST /api/generate/flashcards, /quiz, /summary
│   │   └── health.py             # GET /api/health (with cache stats)
│   └── utils/
│       └── logging_config.py      # Loguru-based logging
├── frontend/
│   ├── index.html                  # Main UI (dark glassmorphism + markdown chat)
│   └── static/
│       ├── css/style.css           # Full design system (education palette + markdown)
│       └── js/app.js               # Chat, model switching, keyboard shortcuts
├── data/
│   ├── faiss_index/                # FAISS vector store (auto-created)
│   ├── uploads/                    # Uploaded files (auto-created)
│   └── logs/                       # Application logs (auto-created)
├── requirements.txt
├── .env                            # Your local config (never commit!)
└── README.md
```

---

## ⚙️ Setup & Installation

### 1. Prerequisites

| Tool | Purpose | Install |
| ---- | ------- | ------- |
| Python 3.10+ | Backend runtime | [python.org](https://python.org) |
| Ollama | Local LLM server | [ollama.com](https://ollama.com) |
| Git | Version control | [git-scm.com](https://git-scm.com) |

### 2. Install Ollama & Pull Models

```bash
# After installing Ollama, pull the models:
ollama pull llama3
ollama pull llama3.1:8b
```

### 3. Create Virtual Environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure Environment

```bash
# Copy the example config
cp .env.example .env
```

Edit `.env` and fill in your keys:

```env
# Required for Ollama (local)
OLLAMA_MODEL=llama3
OLLAMA_BASE_URL=http://localhost:11434

# Google Gemini API — FREE (get key at https://aistudio.google.com/apikey)
GEMINI_API_KEY=your_gemini_key_here

# OpenRouter API — FREE (get key at https://openrouter.ai)
OPENROUTER_API_KEY=your_openrouter_key_here

# OpenAI — Paid fallback (optional)
OPENAI_API_KEY=sk-your-openai-key-here
```

### 6. Start the Server

```bash
python -m uvicorn app.main:app --reload
```

Open <http://localhost:8000> in your browser.

---

## 🤖 Multi-Model Support

Easy-Study supports **4 LLM providers** — switch between them in real-time via the header dropdown:

### Ollama (Local — Free)

Runs models on your machine. No internet required.

| Model | Size | Best For |
| ----- | ---- | -------- |
| `llama3:latest` | 4.7 GB | General Q&A, summaries |
| `llama3.1:8b` | 4.9 GB | Better reasoning, longer context |

### Gemini (Cloud — Free)

Google's Gemini API. Fast, high quality, no credit card needed.

| Model | Description |
| ----- | ----------- |
| `gemini-2.5-flash` | Latest and fastest Flash model |
| `gemini-2.0-flash` | Balanced speed and quality |
| `gemini-2.0-flash-lite` | Lightweight, highest throughput |

> **Get a free API key:** <https://aistudio.google.com/apikey> → Sign in with Google → Create key → Paste in `.env`

### OpenRouter (Cloud — Free Open-Source)

Runs open-source models completely free. No credit card required.

| Model | Description |
| ----- | ----------- |
| `llama-3.3-70b-free` | Most capable — 70B Llama |
| `llama-4-scout-free` | Llama 4 Scout 17B |
| `deepseek-r1-free` | DeepSeek R1 reasoning model |
| `gemma-3-27b-free` | Google Gemma 3 27B |
| `qwen3-8b-free` | Alibaba's Qwen3 8B |
| `mistral-small-free` | Mistral Small 3.1 24B |

> **Get a free API key:** <https://openrouter.ai> → Sign up → Keys → Create → Paste in `.env`

### OpenAI (Cloud — Paid)

Used as automatic fallback when confidence is low.

| Model | Description |
| ----- | ----------- |
| `gpt-4o-mini` | Cost-effective, high quality |

---

## 🚀 API Reference

| Endpoint | Method | Description |
| -------- | ------ | ----------- |
| `/api/health` | GET | System status and component health |
| `/api/models` | GET | List all available providers & models |
| `/api/models/active` | GET | Get currently active provider & model |
| `/api/models/switch` | POST | Switch AI model `{"provider":"gemini","model":"gemini-2.0-flash"}` |
| `/api/upload` | POST | Upload PDF or text file |
| `/api/ingest/url` | POST | Ingest article URL or YouTube link |
| `/api/ingest/text` | POST | Save raw text / notes |
| `/api/query` | POST | Ask a question (full RAG pipeline) |
| `/api/generate/flashcards` | POST | Generate flashcards from knowledge base |
| `/api/generate/quiz` | POST | Generate multiple-choice quiz |
| `/api/generate/summary` | POST | Generate summary with key points |
| `/docs` | GET | Interactive Swagger UI |

### Example: Switch Model

```bash
curl -X POST http://localhost:8000/api/models/switch \
  -H "Content-Type: application/json" \
  -d '{"provider": "gemini", "model": "gemini-2.0-flash"}'
```

### Example: Upload PDF

```bash
curl -X POST http://localhost:8000/api/upload \
  -F "file=@notes.pdf" \
  -F "source_type=pdf"
```

### Example: Query

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the key concepts explained?", "top_k": 5}'
```

### Example: Generate Flashcards

```bash
curl -X POST http://localhost:8000/api/generate/flashcards \
  -H "Content-Type: application/json" \
  -d '{"topic": "machine learning", "count": 10}'
```

---

## 🔄 System Flow

```text
User Input (PDF / URL / YouTube / Notes)
         ↓
   Input Type Detection
         ↓
   Document Loader (PyPDF / WebBase / YouTube Transcript API)
         ↓
   Text Chunking (500 chars, 100 overlap)
         ↓
   HuggingFace Embeddings (all-MiniLM-L6-v2)
         ↓
   FAISS Vector Store (save_local)
         ↓
───────────────────────────────
   User Query
         ↓
   Query → Embedding
         ↓
   FAISS Similarity Search (Top-K)
         ↓
   Confidence Check (score ≥ 0.35 ?)
     ├─ YES → Active Model (Gemini/OpenRouter/Ollama/OpenAI) + RAG Context → Answer
     └─ NO  → Smart Fallback Chain (Gemini → OpenRouter → OpenAI) → Answer
         ↓
   Return JSON with answer + sources + model info + confidence
```

---

## 🧩 Module Summary

| Module | File | Responsibility |
| ------ | ---- | -------------- |
| 1 – Input Handler | `ingestion.py` | Detects input type (PDF/URL/YT/text) |
| 2 – Data Ingestion | `ingestion.py` | Loads documents from each source |
| 3 – Text Processing | `vector_store.py` | Recursive character text splitting |
| 4 – Embedding Gen | `vector_store.py` | HuggingFace sentence-transformers |
| 5 – Vector DB | `vector_store.py` | FAISS local index (create + merge) |
| 6 – Retrieval | `vector_store.py` | Similarity search with scores |
| 7 – LLM Response | `llm_engine.py` | Multi-provider LLM engine (Gemini, OpenRouter, Ollama, OpenAI) |
| 8 – Confidence Check | `llm_engine.py` | Weighted score threshold gating |
| 9 – Fallback AI | `llm_engine.py` | Smart fallback chain (Gemini → OpenRouter → OpenAI) |
| 10 – Model Manager | `llm_engine.py` | Runtime provider/model switching |
| 11 – Study Tools | `study_tools.py` | Flashcard, quiz & summary generation |

---

## 🛠️ Configuration Options (`.env`)

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `OLLAMA_MODEL` | `llama3` | Default local LLM model name |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `GEMINI_API_KEY` | — | Gemini API key (free at aistudio.google.com) |
| `OPENROUTER_API_KEY` | — | OpenRouter API key (free at openrouter.ai) |
| `OPENAI_API_KEY` | — | OpenAI API key (paid, for fallback) |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | HuggingFace model |
| `CHUNK_SIZE` | `1000` | Text chunk size (characters) |
| `CHUNK_OVERLAP` | `200` | Overlap between chunks |
| `TOP_K_RESULTS` | `5` | Max retrieved context chunks |
| `CONFIDENCE_THRESHOLD` | `0.50` | Min score to avoid fallback |

---

## 🎨 Design Philosophy

The UI uses an **education-optimized color palette** based on color psychology research:

| Color | Usage | Psychology |
| ----- | ----- | ---------- |
| **Deep Navy** `#0B1120` | Background | Reduces eye strain for long study sessions |
| **Blue** `#3B82F6` | Primary accent | Promotes focus, trust, and calm |
| **Emerald** `#10B981` | Secondary accent | Growth, progress, and harmony |
| **Amber** `#F59E0B` | Warnings/highlights | Draws attention without stress |

> Inspired by platforms like Duolingo, D2L, and Academia. Based on research from [Verpex](https://verpex.com/blog/best-color-combinations-for-educational-websites) and SAGE color psychology studies.

---

## 🗺️ Development Roadmap

- [x] Phase 1 – PDF RAG pipeline
- [x] Phase 2 – Multi-source ingestion (URL, Notes)
- [x] Phase 3 – YouTube transcript integration
- [x] Phase 4 – Confidence-based fallback AI
- [x] Phase 5 – Multi-model support (Gemini, OpenRouter, Ollama, OpenAI)
- [x] Phase 6 – Study tools (Flashcards, Quizzes, Summaries)
- [x] Phase 7 – Education-friendly UI redesign
- [x] Phase 8 – Chat history persistence (localStorage)
- [x] Phase 9 – In-memory LRU response cache
- [x] Phase 10 – Markdown rendering in chat
- [x] Phase 11 – Keyboard shortcuts & Pydantic schemas
- [x] Phase 12 – FAISS in-memory caching + thread safety
- [ ] Phase 13 – Streaming responses (SSE)
- [ ] Phase 14 – SQLite/Redis metadata storage
- [ ] Phase 15 – User authentication & sessions
- [ ] Phase 16 – Source deduplication & management
- [ ] Phase 17 – Docker containerization

---

## 📄 License

This project is for educational purposes.

---

**Built with ❤️ for students who want to learn smarter, not harder.**
