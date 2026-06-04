import logging

import requests

from backend.config import settings
from backend.generation.context_builder import build_context
from backend.prompts import build_greeting_prompt, build_user_prompt

logger = logging.getLogger(__name__)

GREETINGS = {"hi", "hello", "hey", "hii", "hiii", "yo", "sup", "greetings"}


def _call_ollama(prompt: str) -> str:
    response = requests.post(
        settings.ollama_url,
        json={"model": settings.ollama_model, "prompt": prompt, "stream": False},
        timeout=120,
    )
    response.raise_for_status()
    return response.json().get("response", "No response from model.").strip()


def _format_sources(context_chunks: list[dict]) -> list[dict]:
    sources: list[dict] = []
    seen: set[tuple] = set()
    for chunk in context_chunks:
        key = (chunk.get("document", "PhD Regulations"), chunk["page"])
        if key not in seen:
            sources.append({"document": key[0], "page": key[1]})
            seen.add(key)
    return sorted(sources, key=lambda s: s["page"])


def ask(question: str, context_chunks: list[dict]) -> dict:
    """Generate an answer using Ollama with RAG context."""
    if question.strip().lower().rstrip("!., ") in GREETINGS:
        prompt = build_greeting_prompt(question)
        answer = _call_ollama(prompt)
        return {"answer": answer, "sources": []}

    context = build_context(context_chunks)
    prompt = build_user_prompt(question, context)

    logger.debug("Sending prompt to Ollama (%d chars)", len(prompt))
    answer = _call_ollama(prompt)

    return {
        "answer": answer,
        "sources": _format_sources(context_chunks),
    }
