import logging
import json
from backend.prompts import QUERY_REWRITER_PROMPT

logger = logging.getLogger(__name__)

async def rewrite_query(question: str, history: list[dict] = None) -> list[str]:
    """Intercepts the raw question and splits it into optimized search queries."""
    from backend.generation.llm import _call_ollama
    
    # Heuristic to bypass the LLM entirely for simple, standalone questions
    if not history:
        q_lower = question.lower()
        words = q_lower.split()
        has_conjunctions = any(word in words for word in ["and", "or", "also"])
        has_multiple_questions = "?" in question.strip()[:-1]
        
        logger.debug(f"DEBUG REWRITER: history={history}")
        logger.debug(f"DEBUG REWRITER: question='{question}'")
        logger.debug(f"DEBUG REWRITER: words={words}")
        logger.debug(f"DEBUG REWRITER: has_conjunctions={has_conjunctions}")
        logger.debug(f"DEBUG REWRITER: has_multiple_questions={has_multiple_questions}")
        
        if not has_conjunctions and not has_multiple_questions:
            logger.info("Bypassing query rewriter for simple single question.")
            return [question.strip()]
            
        logger.debug("DEBUG REWRITER: Heuristic failed! Falling back to LLM.")
    if history:
        # Format history as a block of text to prevent the model from treating it as a conversational chat
        history_str = "\n".join([f"{msg['role'].capitalize()}: {msg['content']}" for msg in history[-4:]]) # Keep last 4 messages for context
        user_prompt = f"Previous Chat Context:\n{history_str}\n\nLatest User Question: \"{question}\"\n\nBased on the context, rewrite the Latest User Question into standalone search queries.\nOutput:"
    else:
        user_prompt = f"Latest User Question: \"{question}\"\nOutput:"
    
    response = await _call_ollama(QUERY_REWRITER_PROMPT, user_prompt)
    logger.debug(f"Raw Rewriter Output:\n{response}")
    
    try:
        clean_json = response.strip()
        if clean_json.startswith("```json"):
            clean_json = clean_json[7:]
        elif clean_json.startswith("```"):
            clean_json = clean_json[3:]
        if clean_json.endswith("```"):
            clean_json = clean_json[:-3]
        clean_json = clean_json.strip()

        queries = json.loads(clean_json)
        
        if isinstance(queries, list) and all(isinstance(q, str) for q in queries):
            return queries
            
    except Exception as e:
        logger.warning(f"Query rewrite failed. Falling back to raw question. Error: {e}\nRaw: {response}")
    
    return [question.strip()]
