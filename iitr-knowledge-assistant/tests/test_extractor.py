import asyncio
import os
import sys

sys.path.append(os.getcwd())

from backend.generation.llm import _call_ollama
from backend.prompts import EVIDENCE_EXTRACTOR_PROMPT

async def main():
    q = "What is the minimum duration required for a PhD?"
    chunk = """(2) Minimum Duration for Thesis Submission\nThe minimum working period for the submission of thesis for a full-time Ph.D. student is two years from the date of candidacy. For a part-time student the minimum working period for the submission of thesis shall be three years from the date of candidacy."""
    
    user_prompt = f"Question: {q}\n\nContext:\n{chunk}"
    res = await _call_ollama(EVIDENCE_EXTRACTOR_PROMPT, user_prompt)
    print("EXTRACTOR OUTPUT:")
    print(res)

asyncio.run(main())
