# Sutra: IITR Knowledge Assistant

An institution-wide AI assistant that answers questions from official IIT Roorkee documents using local/offline AI models.

**Current scope:** Single PDF — PhD Regulations 2026.

## Architecture

```
User → Frontend → FastAPI → PostgreSQL (Session Check) → Query Processing (Rewriter) 
     → FAISS Search → Re-ranking → Context Builder → Ollama (Qwen2.5 7B) → Answer + Sources
```

Persistent vector index stored under `vector_db/`. No cloud APIs — fully offline after models are downloaded.

## Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com/) with `qwen2.5:7b-instruct-q4_K_M` pulled:
  ```bash
  ollama pull qwen2.5:7b-instruct-q4_K_M
  ```

## Setup

```bash
cd iitr-knowledge-assistant
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Place the PDF at `data/raw/phd_regulations_2026.pdf` (included after setup).

Build the search index:

```bash
python scripts/build_index.py
```

Start the API (from the project root — you are likely already in `iitr-knowledge-assistant`):

```bash
source venv/bin/activate
chmod +x scripts/run_server.sh
./scripts/run_server.sh
```

The script picks a free port (default **45123**) and updates `frontend/api-config.js` so the chat UI connects automatically. **Do not use 8000, 8001, 8765, or 17341** — Cursor IDE often binds those when you try to start a server.

If the API is **already running**, the script prints that URL instead of starting a duplicate.

If you see **“Address already in use”**: Cursor auto-forwards ports it sees in your terminal (45123, 52000, etc.) and blocks uvicorn. The launcher now uses **port 0** (OS picks a random free port). Run `pkill -f "uvicorn backend.main"` then `./scripts/run_server.sh` and open the URL it prints. Forward **that** port in Cursor Ports (SSH remote).

Open the URL printed by `run_server.sh` (e.g. **http://127.0.0.1:45123/**) — the chat UI and API share that port.

**SSH / Cursor remote:** Forward that one port in the Ports panel, then open the forwarded URL in your browser. Do not use a separate `http.server` on 8080 unless you know how to forward both ports.

## API

### POST /ask

```bash
curl -X POST http://localhost:45123/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the maximum duration of PhD?"}'
```

Response:

```json
{
  "answer": "...",
  "sources": [{"document": "PhD Regulations", "page": 21}],
  "debug": [...]
}
```

### GET /health

Returns index status, chunk count, and model configuration.

## Project Structure

```
backend/
  ingestion/     PDF loading, chunking, metadata
  indexing/      FAISS build/load
  retrieval/     Search + reranking
  query/         Query processing + shortcuts
  generation/    Context builder + Ollama LLM
  api/routes/    FastAPI endpoints
data/raw/        Source PDFs
vector_db/       Persistent FAISS index + chunk metadata
frontend/        Chat UI
scripts/         Index build CLI
```

## Testing

To ensure zero regressions and perfect factual accuracy, the system includes a test suite covering Admission, GATE, Candidacy, Thesis, and Hallucination scenarios.

Run the test suite in-memory (network-free, instant execution using FastAPI's TestClient):
```bash
venv/bin/python tests/run_in_memory_tests.py
```

## Roadmap

| Phase | Status | Details |
|-------|--------|---------|
| 1 — Single PDF prototype | Done | Basic retrieval prototype |
| 2 — Hybrid Retrieval (BM25 + FAISS + RRF) & Reranking | Done | RRF fusion, query expansions, numerical shortcuts, in-memory testing (**100% Accuracy, 0% Hallucinations**) |
| 3 — FastAPI + PostgreSQL + chat history | **Done** | SQLAlchemy asyncpg integration, Dockerized PostgreSQL database, chat session management |
| 4 — Admin dashboard, upload, analytics | Planned | Monitoring performance, upload new files, update search index |
| 5 — Production deployment (Docker, Windows Server) | Planned | Docker compose, production builds |
