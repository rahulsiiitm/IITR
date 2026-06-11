import asyncio
from backend.generation.rewriter import rewrite_query

async def main():
    q1 = "Hi bot, please tell me if I will be kicked out if I take too long?"
    print(f"Q: {q1}")
    r1 = await rewrite_query(q1)
    print(f"R: {r1}\n")

    q2 = "Who is the boss of my guide?"
    print(f"Q: {q2}")
    r2 = await rewrite_query(q2)
    print(f"R: {r2}\n")

asyncio.run(main())
