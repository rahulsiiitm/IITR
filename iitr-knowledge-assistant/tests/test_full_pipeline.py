import asyncio
import os
import sys
import logging

logging.basicConfig(level=logging.INFO)

sys.path.append(os.getcwd())

from backend.generation.llm import extract_evidence, generate_from_evidence
from backend.generation.rewriter import rewrite_query
from backend.query.processor import retrieve_candidates, select_reranked_per_page
from backend.retrieval.rerank import expand_context
import json

async def main():
    with open("vector_db/metadata/chunks.json", "r") as f:
        chunks = json.load(f)
        
    import faiss
    index = faiss.read_index("vector_db/indexes/faiss.index")
    
    question = "minimum duration?"
    history = []
    
    search_queries = await rewrite_query(question, history)
    print("QUERIES:", search_queries)
    
    all_expanded = []
    all_evidence = []
    seen_texts = set()

    for q in search_queries:
        candidates = retrieve_candidates(q, index, chunks)
        reranked, _ = select_reranked_per_page(q, candidates)
        expanded = expand_context(reranked, chunks)

        for chunk in expanded:
            chunk_text = chunk.get("chunk", "")
            if chunk_text not in seen_texts:
                seen_texts.add(chunk_text)
                all_expanded.append(chunk)

        evidence_text = await extract_evidence(q, reranked[:2])
        print("EXTRACTED EVIDENCE FOR Q:", q)
        print(evidence_text)
        if evidence_text and "NO_EVIDENCE" not in evidence_text.upper():
            all_evidence.append(evidence_text)

    all_expanded = sorted(all_expanded, key=lambda c: c.get("page", 0))
    merged_evidence = "\n\n".join(all_evidence) if all_evidence else "NO_EVIDENCE"
    print("MERGED EVIDENCE:", merged_evidence)
    
    result = await generate_from_evidence(question, merged_evidence, all_expanded, history)
    print("FINAL ANSWER:", result["answer"])

asyncio.run(main())
