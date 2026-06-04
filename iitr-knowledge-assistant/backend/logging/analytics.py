import json
import logging
import time
from typing import Any

logger = logging.getLogger("iitr.analytics")


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def log_ask_request(
    question: str,
    latency_ms: float,
    candidate_count: int,
    reranked_count: int,
    expanded_count: int,
    confidence_passed: bool,
    model_used: str,
    rerank_scores: list[float] | None = None,
) -> None:
    payload: dict[str, Any] = {
        "event": "ask",
        "question": question,
        "latency_ms": round(latency_ms, 2),
        "candidate_count": candidate_count,
        "reranked_count": reranked_count,
        "expanded_count": expanded_count,
        "confidence_passed": confidence_passed,
        "model_used": model_used,
        "rerank_scores": rerank_scores or [],
    }
    logger.info(json.dumps(payload))


class RequestTimer:
    def __init__(self) -> None:
        self._start = time.perf_counter()

    @property
    def elapsed_ms(self) -> float:
        return (time.perf_counter() - self._start) * 1000
