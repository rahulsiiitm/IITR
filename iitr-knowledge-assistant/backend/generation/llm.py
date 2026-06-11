import logging
import re
from typing import AsyncGenerator
import httpx

from backend.config import settings
from backend.generation.context_builder import build_context
from backend.prompts import EVIDENCE_EXTRACTOR_PROMPT, SYSTEM_PROMPT, VERIFIER_PROMPT, build_greeting_prompt, build_user_prompt
from backend.generation.rewriter import rewrite_query

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
                    "num_predict": 1500,
                },
            },
        )
        response.raise_for_status()
        data = response.json()
        # /api/chat returns {"message": {"role": "assistant", "content": "..."}}
        msg = data.get("message", {})
        return msg.get("content", data.get("response", "No response from model.")).strip()


async def _stream_ollama(
    system: str,
    user: str,
    history: list[dict] = None,
) -> AsyncGenerator[str, None]:
    """Stream tokens from Ollama /api/chat as an async generator of content strings."""
    messages = [{"role": "system", "content": system}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user})

    async with httpx.AsyncClient(timeout=400.0) as client:
        async with client.stream(
            "POST",
            settings.ollama_url,
            json={
                "model": settings.ollama_model,
                "messages": messages,
                "stream": True,
                "options": {
                    "temperature": 0.0,
                    "repeat_penalty": 1.1,
                    "num_predict": 1500,
                },
            },
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                import json as _json
                try:
                    chunk = _json.loads(line)
                except Exception:
                    continue
                token = chunk.get("message", {}).get("content", "")
                if token:
                    yield token
                if chunk.get("done"):
                    break


def _format_sources(context_chunks: list[dict]) -> list[dict]:
    sources: list[dict] = []
    seen: set[tuple] = set()
    for chunk in context_chunks:
        key = (chunk.get("document", "PhD Regulations"), chunk["page"])
        if key not in seen:
            sources.append({"document": key[0], "page": key[1]})
            seen.add(key)
    return sorted(sources, key=lambda s: s["page"])


async def extract_evidence(question: str, context_chunks: list[dict]) -> str:
    """Extract evidence from context chunks for a specific query."""
    context = build_context(context_chunks)
    if context_chunks:
        print(f"Retrieving evidence for: '{question}' (Chunk 1 Length: {len(context_chunks[0].get('chunk', context_chunks[0].get('text', '')))})")
    
    extractor_user = (
        f"Context:\n{context}\n\n"
        f"Question:\n{question}\n\n"
        f"Extract the exact quotes. Begin your response exactly with this tag:\n"
        f"<thinking>"
    )
    evidence = await _call_ollama(EVIDENCE_EXTRACTOR_PROMPT, extractor_user)

    print(f"--- EXTRACTED EVIDENCE for '{question}' ---\n{evidence}\n--------------------------")
    
    match = re.search(r"<evidence>(.*?)</evidence>", evidence, re.DOTALL | re.IGNORECASE)
    evidence_text = match.group(1).strip() if match else evidence.strip()
    return evidence_text


async def generate_from_evidence(question: str, evidence_text: str, context_chunks: list[dict], history: list[dict] = None) -> dict:
    """Generate final answer using the aggregated evidence."""
    if "NO_EVIDENCE" in evidence_text.upper() or not evidence_text.strip():
        return {
            "answer": "The regulations do not explicitly state this.",
            "sources": _format_sources(context_chunks),
        }

    # Step 2: Answer Generation using ONLY Evidence
    user_prompt = build_user_prompt(question, evidence_text)
    logger.debug("Sending prompt to Ollama (%d chars system, %d chars user)",
                 len(SYSTEM_PROMPT), len(user_prompt))
    answer = await _call_ollama(SYSTEM_PROMPT, user_prompt, history)

    if "Answer:" in answer:
        answer = answer.split("Answer:")[-1].strip()

    # Step 3: Pure LLM-Based Verification
    verifier_user = f"Question:\n{question}\n\nEvidence:\n{evidence_text}\n\nAnswer:\n{answer}"
    verdict = await _call_ollama(VERIFIER_PROMPT, verifier_user)
    
    if "FAIL" in verdict.upper() and "PASS" not in verdict.upper():
        logger.warning(f"Answer verification failed by LLM. Verdict:\n{verdict}")
        return {
            "answer": "The regulations do not explicitly state this.",
            "sources": _format_sources(context_chunks),
        }

    return {
        "answer": answer,
        "sources": _format_sources(context_chunks),
    }


async def stream_answer_from_evidence(
    question: str,
    evidence_text: str,
    context_chunks: list[dict],
    history: list[dict] = None,
) -> AsyncGenerator[str, None]:
    """Stream the final answer token-by-token.

    Yields string tokens as they arrive from Ollama.  The verifier step is
    intentionally omitted here — it requires the complete answer which defeats
    streaming.  Strict evidence extraction upstream prevents hallucination.
    """
    if "NO_EVIDENCE" in evidence_text.upper() or not evidence_text.strip():
        yield "The regulations do not explicitly state this."
        return

    user_prompt = build_user_prompt(question, evidence_text)
    buffer = ""
    answer_started = False

    async for token in _stream_ollama(SYSTEM_PROMPT, user_prompt, history):
        if answer_started:
            # Already past the prefix — stream tokens directly
            yield token
        else:
            buffer += token
            if "Answer:" in buffer:
                # Strip everything up to and including "Answer:" then flush remainder
                remainder = buffer.split("Answer:", 1)[-1]
                buffer = ""
                answer_started = True
                if remainder:
                    yield remainder
            elif len(buffer) > 50:
                # No "Answer:" prefix found — flush the whole buffer and start streaming
                answer_started = True
                yield buffer
                buffer = ""
