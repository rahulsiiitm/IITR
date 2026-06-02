import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "mistral:latest"

SYSTEM_PROMPT = """You are an IIT Roorkee PhD regulations assistant.

Read every context chunk carefully.

If any chunk contains information relevant to the question, use it to answer.

Do not require an exact sentence match.

When eligibility depends on numerical thresholds (CGPA, percentage, marks, attempts, duration, etc.):

1. Extract the exact threshold from the document.
2. Compare the user's value with the threshold.
3. State whether the requirement is met.
4. Never assume eligibility without checking the numerical condition.
5. Treat 7.99 as less than 8.0, 8.0 as equal to 8.0, and 8.01 as greater than 8.0.

When answering:

- Prefer the shortest correct answer.
- Do not repeat the question.
- Do not add unnecessary explanations.
- Do not provide recommendations unless explicitly asked.
- Only include information supported by the document.

Question Length Rules:

1. Simple factual questions
   (full forms, definitions, numbers, limits, dates, eligibility thresholds):
   - Answer in 1 sentence only.

2. Eligibility questions involving user data:
   - Answer in 1–2 sentences maximum.

3. Process or procedural questions:
   - Answer in 2–4 concise bullet points.

4. Compound questions with multiple sub-parts:
   - Identify every sub-question.
   - Use numbered headings.
   - Answer each sub-question in 1–2 sentences maximum.
   - Do not skip any sub-question if relevant information exists.

When providing the answer:

- Be precise.
- Include important qualifying details when necessary.
- If a rule applies to specific categories (e.g., IITs, CFTIs, SC/ST/PWD), mention them.
- Never mention "DOCUMENT CHUNK" in the response.
- Refer only to "the document" or "the regulations" if needed.

Only respond with exactly:

Information not available in the document

when no relevant information exists.

Greetings:

If the user sends a greeting (hi, hello, hey, etc.), respond with a brief greeting and ask how you can help. Do not use document context for greetings.

Examples:

Question:
What does SGPA stand for?

Answer:
SGPA stands for Semester Grade Point Average.

Question:
What is SRC?

Answer:
SRC stands for Student Research Committee.

Question:
How many co-supervisors can a student have?

Answer:
A student can have at most two co-supervisors, with not more than one from outside the Institute.

Question:
I graduated from IIT with a CGPA of 7.9. Do I qualify for GATE exemption?

Document:
IIT graduates with a CGPA of 8.0 and above are exempted from GATE.

Answer:
No. The exemption requires a CGPA of 8.0 or above, and 7.9 does not meet this requirement.

Question:
I graduated from IIT with a CGPA of 7.99. Do I qualify for GATE exemption? What coursework requirements apply?

Document:
IIT graduates with a CGPA of 8.0 and above are exempted from GATE.
Coursework requires a CGPA of at least 7.00.

Answer:
1. GATE Exemption: No. The exemption requires a CGPA of 8.0 or above, and 7.99 does not meet this requirement.
2. Coursework: Required coursework and seminar credits must be completed with a CGPA of at least 7.00.

IMPORTANT:
Prefer the shortest correct answer.
"""

def ask(question, context_chunks):
    """Send a question with RAG context to the LLM.
    
    Args:
        question: User question string
        context_chunks: List of reranked dicts [{"chunk": "...", "page": 1, "rerank_score": ...}, ...]
    
    Returns:
        dict: {"answer": "...", "sources": [1, 3]}
    """
    # Handle greetings — skip context entirely
    greetings = ["hi", "hello", "hey", "hii", "hiii", "yo", "sup", "greetings"]
    if question.strip().lower().rstrip("!., ") in greetings:
        prompt = f"""{SYSTEM_PROMPT}

The user said: "{question}"

Respond with a brief, friendly greeting and ask how you can help with PhD admission queries."""

        response = requests.post(OLLAMA_URL, json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False
        })
        response.raise_for_status()
        answer = response.json().get("response", "No response from model.")

        return {
            "answer": answer.strip(),
            "sources": []
        }

    # Build context using full page text (deduplicated by page)
    context = ""
    seen_pages = set()

    for c in context_chunks:
        page_num = c["page"]
        if page_num not in seen_pages:
            context += f"""
PAGE {page_num}

{c.get('full_page', c['chunk'])}
"""
            seen_pages.add(page_num)

    prompt = f"""{SYSTEM_PROMPT}

Context:
{context}

Question:
{question}"""

    # If question mentions numerical constraints, add dynamic guidance
    if any(word in question.lower() for word in ["cgpa", "marks", "percentage", "attempt", "year"]):
        prompt += """

Note: Pay special attention to numerical conditions:
- Compare values mathematically and carefully.
- 7.99 is strictly less than 8.0.
- 8.0 satisfies a requirement of 8.0 or above.
- Do not approximate numerical thresholds (e.g. 7.99 does NOT round up to 8.0).
- Explain if the user's score meets the exact threshold."""

    # Dynamic target-phrasing warning for exemption vs requirement logic
    q_lower = question.lower()
    if any(phrase in q_lower for phrase in ["need gate", "require gate", "gate required", "need a test", "require a test"]):
        prompt += """

Note: The user is asking if they NEED a national level test (like GATE) or if it is REQUIRED.
- If the regulations exempt them, answer "No, you do not need GATE / GATE is not required."
- If the regulations do not exempt them, answer "Yes, you need GATE / GATE is required."
- Pay close attention to this logical negation."""
    elif "exempt" in q_lower:
        prompt += """

Note: The user is asking if they qualify for an EXEMPTION.
- If the regulations exempt them, answer "Yes, you are exempted from qualifying in GATE/NET."
- If the regulations do not exempt them, answer "No, you are not exempted from GATE/NET." """

    # If compound question is detected, force numbered headings
    # Count question marks or use sub_questions length
    import re
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', question) if s.strip()]
    if len(sentences) > 1:
        prompt += """

Note: The user has asked a compound question with multiple sub-questions.
- You MUST answer each sub-question separately using numbered headings (e.g., 1. GATE Exemption, 2. Admission Eligibility, 3. Coursework, 4. Candidacy, 5. Thesis Submission).
- Make sure to explicitly address every single sub-part of the question under its corresponding numbered heading."""

    prompt += "\n\nAnswer:"

    print("--- SENDING PROMPT TO MISTRAL ---")
    print(prompt)
    print("---------------------------------")

    response = requests.post(OLLAMA_URL, json={
        "model": MODEL,
        "prompt": prompt,
        "stream": False
    })
    response.raise_for_status()
    answer = response.json().get("response", "No response from model.")

    # Only include source pages from the reranked chunks (not all 10)
    sources = sorted(set(c["page"] for c in context_chunks))

    return {
        "answer": answer.strip(),
        "sources": sources
    }
