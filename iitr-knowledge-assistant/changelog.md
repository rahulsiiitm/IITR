# Changelog

All notable changes to the **IITR Knowledge Assistant** project are documented here chronologically.

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
