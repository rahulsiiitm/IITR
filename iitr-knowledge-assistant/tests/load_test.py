import asyncio
import httpx
import time
import sys
from backend.config import settings

async def fetch(client, url, payload, headers):
    try:
        start = time.time()
        response = await client.post(url, json=payload, headers=headers)
        return response.status_code, time.time() - start
    except Exception as e:
        return str(e), 0

async def main():
    url = "http://127.0.0.1:45123/ask"
    headers = {"X-API-Key": settings.api_key} if settings.api_key else {}
    payload = {"question": "Hello!"}
    
    num_requests = 100
    print(f"🚀 Starting load test: {num_requests} concurrent requests to {url}")
    start_time = time.time()
    
    limits = httpx.Limits(max_connections=200, max_keepalive_connections=200)
    async with httpx.AsyncClient(limits=limits) as client:
        tasks = [fetch(client, url, payload, headers) for _ in range(num_requests)]
        results = await asyncio.gather(*tasks)
        
    duration = time.time() - start_time
    
    successes = sum(1 for r, _ in results if r == 200)
    failures = len(results) - successes
    
    print(f"\n📊 Load Test Results:")
    print(f"------------------------")
    print(f"Total Time:  {duration:.2f} seconds")
    print(f"Requests:    {num_requests}")
    print(f"Successes:   {successes}")
    print(f"Failures:    {failures}")
    if duration > 0:
        print(f"Throughput:  {num_requests / duration:.2f} req/sec")

if __name__ == "__main__":
    asyncio.run(main())
