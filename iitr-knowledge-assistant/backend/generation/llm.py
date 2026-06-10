import re
import logging

import httpx

from backend.config import settings
from backend.generation.context_builder import build_context
from backend.prompts import EVIDENCE_EXTRACTOR_PROMPT, SYSTEM_PROMPT, VERIFIER_PROMPT, build_greeting_prompt, build_user_prompt

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
                    "num_predict": 1000,
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
    if context_chunks:
        print(f"Retrieved Chunk 1 Length: {len(context_chunks[0].get('chunk', context_chunks[0].get('text', '')))}")
    # Step 1: Evidence Extraction
    extractor_user = f"Context:\n{context}\n\nQuestion:\n{question}\n\nQuotations:"
    raw_evidence = await _call_ollama(EVIDENCE_EXTRACTOR_PROMPT, extractor_user)

    print(f"--- EXTRACTED EVIDENCE ---\n{raw_evidence}\n--------------------------")
    
    match = re.search(r'<(?:evidence|quotation)>(.*?)</(?:evidence|quotation)>', raw_evidence, re.DOTALL | re.IGNORECASE)
    evidence_text = match.group(1).strip() if match else raw_evidence.strip()

    if "NO_EVIDENCE" in evidence_text.upper() or not evidence_text:
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
