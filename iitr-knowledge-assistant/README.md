# IITR Knowledge Assistant

An institution-wide AI assistant that answers questions from official IIT Roorkee documents using local/offline AI models.

**Current scope:** Single PDF — PhD Regulations 2026.

## Architecture

```
User → Frontend → FastAPI → Query Processing → FAISS Search → Re-ranking
     → Context Builder → Ollama (Mistral) → Answer + Sources
```

Persistent vector index stored under `vector_db/`. No cloud APIs — fully offline after models are downloaded.

## Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com/) with `mistral:latest` pulled:
  ```bash
  ollama pull mistral:latest
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

Start the API:

```bash
uvicorn backend.main:app --reload --port 8000
```

Serve the frontend (any static file server), e.g.:

```bash
cd frontend && python -m http.server 8080
```

Open `http://localhost:8080` in your browser.

## API

### POST /ask

```bash
curl -X POST http://localhost:8000/ask \
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

## Roadmap

| Phase | Status |
|-------|--------|
| 1 — Single PDF prototype | Done (Test_Chatbot) |
| 2 — Layered architecture, persistent FAISS | **Current** |
| 3 — FastAPI + PostgreSQL + chat history | Planned |
| 4 — Admin dashboard, upload, analytics | Planned |
| 5 — Production deployment (Docker, Windows Server) | Planned |
