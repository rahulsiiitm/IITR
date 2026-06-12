# Sutra - IITR Knowledge Assistant

> An institution-wide AI assistant that answers questions grounded in official IIT Roorkee documents, powered entirely by local/offline models. No cloud APIs. No hallucinations on out-of-scope questions.

**Current scope:** PhD Regulations 2026 (single PDF, multi-query RAG pipeline).

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Local Setup (Dev)](#local-setup-dev)
- [Docker Deployment](#docker-deployment)
- [API Reference](#api-reference)
- [Admin Dashboard](#admin-dashboard)
- [Configuration](#configuration)
- [Testing](#testing)
- [Roadmap](#roadmap)

---

## Features

- 🔍 **Hybrid RAG pipeline** — BM25 + FAISS vector search with cross-encoder reranking
- 🧠 **Multi-query rewriting** — expands queries into sub-questions for higher recall
- 🎯 **Intent routing** — local zero-shot classifier separates conversational vs. regulatory queries; skips RAG for off-topic prompts
- 💬 **Streaming responses** — SSE token-by-token streaming to the browser
- 🗂️ **Session memory** — PostgreSQL-backed persistent chat history across sessions
- 🛡️ **Hallucination mitigation** — entity blocking, confidence thresholds, strict prompt engineering
- 📊 **Admin dashboard** — live session browser, system metrics, config viewer, bulk delete
- 🐳 **Dockerised** — single `docker-compose up` spins up the API + PostgreSQL

---

## Architecture

```
Browser
  │
  ▼
FastAPI (port 45123)
  ├── GET  /           → Chat UI (index.html)
  ├── POST /ask/stream → Streaming RAG answer (SSE)
  ├── POST /ask        → Non-streaming RAG answer
  ├── GET  /api/admin/* → Admin dashboard API
  └── GET  /health     → Health check
        │
        ├── Intent Classifier (local zero-shot, transformers)
        │     ├── Conversational → LLM direct answer (no RAG)
        │     └── Regulatory     → RAG pipeline ↓
        │
        ├── Query Rewriter (Ollama → sub-questions)
        │
        ├── Hybrid Retriever
        │     ├── BM25  (rank-bm25)
        │     └── FAISS (sentence-transformers: BAAI/bge-base-en-v1.5)
        │     └── RRF fusion
        │
        ├── Cross-encoder Reranker (BAAI/bge-reranker-base)
        │
        ├── Context Builder + Evidence Extractor
        │
        └── Ollama LLM (qwen2.5:7b-instruct-q4_K_M)
              └── Streamed answer + source citations

PostgreSQL ← Session & Message storage (SQLAlchemy asyncpg)
```

No internet required after models are downloaded.

---

## Project Structure

```
iitr-knowledge-assistant/
├── backend/
│   ├── api/
│   │   ├── routes/
│   │   │   ├── ask.py        # /ask and /ask/stream endpoints + API key auth
│   │   │   ├── admin.py      # Admin session/stats/settings endpoints
│   │   │   └── voice.py      # Voice transcription & synthesis (disabled for now)
│   │   └── limiter.py        # Rate limiting (slowapi)
│   ├── ingestion/            # PDF loading & chunking
│   ├── indexing/             # FAISS index build / load
│   ├── retrieval/            # BM25, FAISS search, reranker
│   ├── query/                # Query processor, shortcuts, intent classifier
│   ├── generation/           # LLM wrapper (Ollama), query rewriter, evidence builder
│   ├── services/             # Voice service (Whisper + TTS, disabled)
│   ├── logging/              # Analytics & request logging
│   ├── config.py             # Centralised settings (pydantic-settings)
│   ├── database.py           # Async SQLAlchemy engine & session
│   ├── models.py             # ORM models: Session, Message
│   └── init_db.py            # DB table creation with retry logic
├── frontend/
│   ├── index.html            # Chat UI
│   ├── script.js             # Chat logic, SSE streaming, suggestion cards
│   ├── style.css             # Glassmorphic Jarvis-themed CSS
│   ├── api-config.js         # Auto-generated: API URL + key (do not commit)
│   ├── admin.html            # Admin dashboard
│   ├── admin.js              # Admin dashboard logic
│   └── admin.css             # Admin dashboard styles
├── data/
│   └── raw/                  # Source PDFs (phd_regulations_2026.pdf)
├── vector_db/
│   ├── indexes/faiss.index   # Persistent FAISS index
│   └── metadata/chunks.json  # Chunk metadata + BM25 corpus
├── docker/
│   └── Dockerfile
├── docker-compose.yml
├── scripts/
│   ├── build_index.py        # Build/rebuild FAISS + chunk metadata
│   ├── run_server.sh         # Dev launcher
│   └── run_server.py         # Port detection + api-config.js writer
├── tests/                    # JSON test suites + in-memory test runner
├── requirements.txt
└── .env                      # Environment config (see Configuration)
```

---

## Prerequisites

- **Python 3.11+**
- **[Ollama](https://ollama.com/)** running locally with the model pulled:
  ```bash
  ollama pull qwen2.5:7b-instruct-q4_K_M
  ```
- **Docker + Docker Compose** (only needed for the containerised deployment path)

---

## Local Setup (Dev)

### 1. Install dependencies

```bash
cd iitr-knowledge-assistant
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env if needed — defaults work out of the box for local dev
```

### 3. Place the PDF

```
data/raw/phd_regulations_2026.pdf
```

### 4. Build the search index

```bash
python scripts/build_index.py
```

This creates `vector_db/indexes/faiss.index` and `vector_db/metadata/chunks.json`. Only needs to run once (or whenever the PDF changes).

### 5. Start the server

```bash
chmod +x scripts/run_server.sh
./scripts/run_server.sh
```

The launcher binds to **port 45123**, writes `frontend/api-config.js` with the correct URL and API key, and prints the chat URL:

```
  Open chat:  http://127.0.0.1:45123/
  Health:     http://127.0.0.1:45123/health
```

> **Already running?** The script detects the existing server and prints its URL instead of starting a duplicate.

> **SSH / Cursor remote?** Forward port `45123` in the Ports panel, then open the forwarded URL in your browser.

---

## Docker Deployment

### 1. Set your API key

```bash
export API_KEY=your_secret_key_here
```

Or add it to a `.env` file in the project root:

```
API_KEY=your_secret_key_here
```

### 2. Build and start

```bash
docker compose up --build -d
```

This starts:
- **`assistant`** — FastAPI app on port 45123
- **`sutra_postgres`** — PostgreSQL 15 with a persistent named volume (`sutra_pg_data`)

Database tables are created automatically on first start via `init_db.py` (with retry logic to wait for Postgres to be ready).

### 3. Verify

```bash
curl http://localhost:45123/health
```

### 4. Stop

```bash
docker compose down
# To also wipe the database volume:
docker compose down -v
```

> **Ollama on the host:** The container calls Ollama at `http://host.docker.internal:11434/api/chat`. Make sure Ollama is running on your host machine before starting the containers.

---

## API Reference

All endpoints are on the same port as the UI (`45123`). Protected endpoints require the `X-API-Key` header when `API_KEY` is set in the environment.

### `POST /ask/stream` ⭐ Primary endpoint

Streams the answer token-by-token as Server-Sent Events (SSE).

```bash
curl -X POST http://localhost:45123/ask/stream \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_key" \
  -d '{"question": "What is the maximum duration of a PhD programme?", "session_id": null}'
```

**Event types:**

| Event | Fields | Description |
|---|---|---|
| `token` | `content` | One streamed token |
| `done` | `session_id`, `sources` | Final event with citation list |
| `error` | `content` | Pipeline error message |

### `POST /ask`

Non-streaming version. Returns the full answer in one JSON response.

```bash
curl -X POST http://localhost:45123/ask \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_key" \
  -d '{"question": "What CGPA is needed for GATE exemption?"}'
```

```json
{
  "answer": "...",
  "session_id": "abc123",
  "sources": [{"document": "PhD Regulations 2026", "page": 12, "filename": "phd_regulations_2026.pdf"}]
}
```

### `GET /health`

```json
{
  "status": "ok",
  "index_loaded": true,
  "chunk_count": 81,
  "embedding_model": "BAAI/bge-base-en-v1.5",
  "rerank_model": "BAAI/bge-reranker-base",
  "llm_model": "qwen2.5:7b-instruct-q4_K_M"
}
```

---

## Admin Dashboard

Available at **`/admin.html`** (no auth required in test mode).

| Section | Description |
|---|---|
| **Dashboard** | Total sessions, messages, uptime |
| **Sessions** | Browse all chat sessions, view message history |
| **Settings** | Live view of all active configuration values |
| **Danger zone** | Delete individual sessions or purge all data |

---

## Configuration

All config is loaded from environment variables (`.env` for local dev, `docker-compose.yml` for Docker).

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_URL` | `http://localhost:11434/api/chat` | Ollama API endpoint |
| `OLLAMA_MODEL` | `qwen2.5:7b-instruct-q4_K_M` | LLM model name |
| `EMBEDDING_MODEL` | `BAAI/bge-base-en-v1.5` | HuggingFace embedding model |
| `RERANK_MODEL` | `BAAI/bge-reranker-base` | HuggingFace cross-encoder reranker |
| `DATABASE_URL` | `postgresql+asyncpg://...@localhost:5432/sutra_db` | Async PostgreSQL connection string |
| `API_KEY` | *(unset)* | If set, all `/ask*` endpoints require `X-API-Key` header |
| `API_PORT` | `45123` | Server port |
| `TOP_K` | `15` | Candidates retrieved per sub-query |
| `RERANK_TOP_K` | `6` | Top chunks passed to LLM after reranking |
| `CONFIDENCE_THRESHOLD` | `-5.0` | Minimum reranker score to include a chunk |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `DEBUG` | `false` | Enable debug mode |

---

## Testing

The test suite covers: Admission, GATE exemption, Candidacy, Coursework, Thesis, Duration, Hallucination, and Numerical boundary cases.

Run all tests in-memory (no network, no running server needed):

```bash
venv/bin/python tests/run_in_memory_tests.py
```

Or run a specific category:

```bash
venv/bin/python tests/run_fresh_tests.py
```

---

## Roadmap

| Phase | Status | Details |
|---|---|---|
| 1 — Single PDF prototype | ✅ Done | Basic FAISS retrieval |
| 2 — Hybrid Retrieval + Reranking | ✅ Done | BM25 + FAISS + RRF fusion, cross-encoder reranking, numerical shortcuts — **100% accuracy, 0% hallucinations** on test suite |
| 3 — FastAPI + PostgreSQL + streaming | ✅ Done | Async SQLAlchemy, Docker PostgreSQL, SSE streaming, session history |
| 4 — Intent routing + conversational AI | ✅ Done | Local zero-shot classifier, LLM direct path for off-topic queries |
| 5 — Admin dashboard | ✅ Done | Session browser, metrics, config viewer, bulk delete |
| 6 — Voice interaction | 🔧 In progress | Whisper transcription + TTS synthesis (disabled pending integration) |
| 7 — Multi-document support | 📋 Planned | Upload new PDFs, rebuild index per document |
| 8 — Production hardening | 📋 Planned | Auth on admin panel, rate limiting, monitoring |
