import logging

import httpx

from backend.config import settings
from backend.generation.context_builder import build_context
from backend.prompts import SYSTEM_PROMPT, build_greeting_prompt, build_user_prompt

logger = logging.getLogger(__name__)


async def _call_ollama(system: str, user: str, history: list[dict] = None) -> str:
    """Call Ollama /api/chat with proper system and user message roles."""
    messages = [{"role": "system", "content": system}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user})
    async with httpx.AsyncClient(timeout=400.0) as client:
        response = await client.post(
            settings.ollama_url,
            json={
                "model": settings.ollama_model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": 0.0,
                    "repeat_penalty": 1.1,
                    "num_predict": 250,
                },
            },
        )
        response.raise_for_status()
        data = response.json()
        # /api/chat returns {"message": {"role": "assistant", "content": "..."}}
        msg = data.get("message", {})
        return msg.get("content", data.get("response", "No response from model.")).strip()


def _format_sources(context_chunks: list[dict]) -> list[dict]:
    sources: list[dict] = []
    seen: set[tuple] = set()
    for chunk in context_chunks:
        key = (chunk.get("document", "PhD Regulations"), chunk["page"])
        if key not in seen:
            sources.append({"document": key[0], "page": key[1]})
            seen.add(key)
    return sorted(sources, key=lambda s: s["page"])


async def ask(question: str, context_chunks: list[dict], history: list[dict] = None) -> dict:
    """Generate an answer using Ollama with RAG context asynchronously."""
    context = build_context(context_chunks)
    user_prompt = build_user_prompt(question, context)

    logger.debug("Sending prompt to Ollama (%d chars system, %d chars user)",
                 len(SYSTEM_PROMPT), len(user_prompt))
    answer = await _call_ollama(SYSTEM_PROMPT, user_prompt, history)

    if "Answer:" in answer:
        answer = answer.split("Answer:")[-1].strip()

    return {
        "answer": answer,
        "sources": _format_sources(context_chunks),
    }
