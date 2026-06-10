import asyncio
import sys
import os

sys.path.append(os.getcwd())

from backend.api.routes.ask import ask_question

async def main():
    # The new ask_question function takes a QuestionRequest object in FastAPI
    # I should use an HTTP request or adapt it.
    pass

asyncio.run(main())
