import asyncio
import httpx

async def main():
    headers = {"X-API-Key": "iitr_phd_1ba91a19af6978e430e6a172"}
    async with httpx.AsyncClient(timeout=60.0, headers=headers) as client:
        # Question 1
        payload1 = {"question": "what is the minimum duration?"}
        print(f"Sending Q1: {payload1['question']}")
        r1 = await client.post("http://127.0.0.1:45123/ask", json=payload1)
        d1 = r1.json()
        print(f"A1: {d1.get('answer', d1)}\n")
        
        session_id = d1.get("session_id")
        
        # Question 2
        payload2 = {"question": "what if I do it part time?", "session_id": session_id}
        print(f"Sending Q2: {payload2['question']}")
        r2 = await client.post("http://127.0.0.1:45123/ask", json=payload2)
        d2 = r2.json()
        print(f"A2: {d2.get('answer', d2)}\n")

if __name__ == "__main__":
    asyncio.run(main())
