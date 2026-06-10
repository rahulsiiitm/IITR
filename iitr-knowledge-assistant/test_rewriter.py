import asyncio
from backend.generation.rewriter import rewrite_query

async def main():
    q1 = "what is the minimum duration and the fees?"
    print(f"Q: {q1}")
    r1 = await rewrite_query(q1)
    print(f"R: {r1}\n")

    history = [
        {"role": "user", "content": "What is the CGPA requirement for candidacy?"},
        {"role": "assistant", "content": "The CGPA requirement is 7.0."}
    ]
    q2 = "what happens if I get lower than that?"
    print(f"Q: {q2}")
    r2 = await rewrite_query(q2, history=history)
    print(f"R: {r2}\n")

asyncio.run(main())
