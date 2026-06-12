import asyncio
import os
import sys
import logging

logging.basicConfig(level=logging.DEBUG)

sys.path.append(os.getcwd())

from backend.query.processor import expand_query_intent

async def main():
    q = "minimum duration?"
    print("EXPANDED:", expand_query_intent(q))

asyncio.run(main())
