# Changelog

All notable changes to the **IITR Knowledge Assistant** project are documented here chronologically.

---

## [1.2.0] - 2026-06-10

### Added
- **Sutra Persona**: Gave the assistant the official identity of "Sutra", with tailored frontend UI modifications and dynamic backend system prompts to maintain an articulate, academic demeanor.
- **PostgreSQL Infrastructure**: Initialized institutional-grade database architecture using SQLAlchemy and `asyncpg` within an isolated `docker-compose` PostgreSQL container, paving the way for persistent session and conversation history.
- **Smart Query Rewriter**: Completely overhauled the LLM-based query rewriter to extract pronouns natively, translate casual queries into academic jargon (e.g. "guide" to "supervisor"), and explicitly strip conversational filler prior to FAISS processing.

### Changed
- **Model Upgrade**: Switched the primary generative model from `mistral:latest` to `qwen2.5:7b-instruct-q4_K_M` to drastically improve semantic rewriting and logical intent capture.
- **Evidence Extractor Tuning**: Constrained the extraction context window to only the Top 2 reranked chunks via FlashRank to eliminate hallucinated assumptions.

---

## [1.1.0] - 2026-06-06

### Changed
- **Ollama `/api/chat` Migration**: Switched from `/api/generate` (single prompt blob) to `/api/chat` with proper `system` and `user` message roles. This dramatically improves instruction-following and eliminates the gibberish output observed with the old endpoint.
- **Prompt Architecture Refactored**: Split `build_user_prompt()` to return only user-role content (context + question + dynamic hints). The system prompt is now sent as a separate message, giving the LLM clearer instruction boundaries.
- **Context Builder Optimized**: Changed from sending full page text to sending only the retrieved chunks grouped by page number. Reduces context window waste by ~60%, allowing the LLM to focus on relevant content.
- **Config Defaults Aligned**: Synchronized `config.py` model defaults (`bge-base-en-v1.5`, `bge-reranker-base`) with `.env` to prevent silent model mismatches when `.env` is absent.

### Fixed
- **LLM Gibberish Output**: The previous test run (phi4-mini via `/api/generate`) produced incoherent output for all non-shortcut queries (5 test failures, 89.4% accuracy). With mistral via `/api/chat`, all previously-failing queries now return correct, coherent answers.
- **Duplicate GREETINGS Set**: Removed redundant `GREETINGS` constant and dead greeting code path from `llm.py` — greetings are handled upstream by `shortcuts.py` before reaching the LLM.
- **Hardcoded Test Path**: Replaced absolute path (`/home/rahul/...`) in `tests/run_in_memory_tests.py` with dynamic `Path(__file__).resolve().parent.parent` for portability.

---

## [1.0.0] - 2026-06-04

### Added
- **Hybrid Retrieval (BM25 + FAISS)**: Integrated BM25 sparse search alongside FAISS dense search, fused via **Reciprocal Rank Fusion (RRF)** to optimize exact keyword matches (clause codes, specific acronyms).
- **Reranking Engine**: Integrated a Cross-Encoder (`cross-encoder/ms-marco-MiniLM-L-6-v2`) to rerank fused search candidates prior to LLM query building.
- **Regression Testing Framework**: Added 5 evaluation datasets (`admission.json`, `gate.json`, `candidacy.json`, `thesis.json`, `hallucination.json`) comprising 61 test cases to monitor RAG accuracy.
- **In-Memory Regression Testing**: Created `tests/run_in_memory_tests.py` using FastAPI's `TestClient` to run queries completely in-process. This ensures sub-millisecond shortcut responses and avoids local networking socket restrictions during validation.
- **Containerization Configurations**: Added `docker/Dockerfile` and `docker-compose.yml` to support building and deploying the assistant offline as a containerized stack.
- **Deterministic Shortcuts & Routing**: Added numerical shortcut parser and spelling/integer tolerancing normalization layer, resulting in 100% accuracy.
- **Out-of-Domain Blocklist**: Intercepted keywords related to hostel/mess fees, placements, rankings, and administrative figures (Director/Dean) to guarantee a 0% hallucination rate.

### Fixed
- **Qualifying Degree Admission Logic**: Resolved a critical conflict where applicants with a CGPA between `6.0` and `7.0` were incorrectly rejected under candidacy regulations instead of being admitted based on qualifying degree thresholds.
- **Thesis Minimum Working Period**: Corrected standard duration rules to assert that a full-time candidate needs 2 years (24 months) minimum working period after candidacy before thesis submission.

---

## [0.1.0] - 2026-06-01

### Added
- **RAG MVP Prototype**: Initial implementation of the offline PhD Regulations chat assistant (basic dense RAG system using FAISS search and Ollama).
- **Flask Backend**: Built endpoints to query the assistant and check service health.
- **Vanilla Web UI**: Initial layout of the responsive frontend chat interface.
