import asyncio
from backend.generation.rewriter import rewrite_query
import logging

logging.basicConfig(level=logging.DEBUG)

async def test():
    history = [
        {"role": "user", "content": "maximum duration of a phd programme"},
        {"role": "assistant", "content": "The maximum period for the submission of thesis shall be five years for full-time students, and six years for part-time students from the date of initial registration."}
    ]
    question = "can it be reduced"
    result = await rewrite_query(question, history)
    print("FINAL RESULT:", result)

if __name__ == "__main__":
    asyncio.run(test())
