import asyncio
import os
import sys

sys.path.append(os.getcwd())

from backend.generation.llm import generate_from_evidence

async def main():
    q = "minimum duration?"
    evidence = "The minimum working period for the submission of thesis for a full-time Ph.D. student is two years from the date of candidacy. For a part-time student the minimum working period for the submission of thesis shall be three years from the date of candidacy."
    res = await generate_from_evidence(q, evidence, [{"chunk": evidence, "page": 34}], [])
    print("GENERATOR OUTPUT:")
    print(res["answer"])

asyncio.run(main())
