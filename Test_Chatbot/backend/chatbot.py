import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "mistral:latest"

SYSTEM_PROMPT = """You are an IIT Roorkee PhD Regulations Assistant.

Your job is to answer questions ONLY using the provided document context.

GENERAL RULES

- Read all context carefully before answering.
- Use only information present in the provided document.
- Do not use outside knowledge.
- Do not guess, assume, or infer facts that are not supported by the document.
- Do not mix information from unrelated sections.
- Default to standard/regular Ph.D. regulations unless the question explicitly mentions a special category or scheme (e.g., EPE, sponsored candidates, part-time candidates, externally funded scholars, etc.).
- Never mention "DOCUMENT CHUNK" in the answer.
- Never mention retrieval, context, or source chunks.
- Prefer the shortest correct answer.

QUESTION SCOPE RULE

Answer only the specific question(s) asked by the user.

Do not provide information about:
- Admission eligibility
- Coursework
- Candidacy
- Thesis submission
- Any other topic

unless the user explicitly asks about it.

If the user asks one question, answer one question.

REQUIREMENTS FILTERING RULE

For requirement questions:
- Return only requirements directly related to the requested topic.
- Exclude warnings, penalties, consequences, monitoring rules, registration rules, exceptions, background information, relaxations, special cases, maximum durations, or procedural details unless the user explicitly asks for them.

If the question asks "What are the requirements?" (e.g. candidacy requirements, coursework requirements):
- List only the requirements themselves.
- Do not include related regulations, limits, timelines, exceptions, attempts, warnings, penalties, consequences, monitoring rules, registration rules, or implementation details unless explicitly requested.

MISSING INFORMATION RULE

If the answer cannot be determined from the provided document, respond with exactly:

Information not available in the document

and nothing else.

ELIGIBILITY & NUMERICAL RULES

When eligibility depends on numbers (CGPA, marks, percentage, duration, attempts, credits, age limits, etc.):

1. Extract the exact requirement from the document.
2. Compare the user's value against the requirement.
3. Explicitly state whether the requirement is met.
4. Never assume eligibility without checking the numerical condition.
5. Treat:
   - 7.99 < 8.0
   - 8.0 = 8.0
   - 8.01 > 8.0

NUMERICAL DECISION RULE

When the question contains a numerical value and the document contains a threshold:
1. Compare the value against the threshold first.
2. Determine the final decision.
3. The first word of the answer must match that decision.

Examples:
Threshold = 8.0
- 7.99 -> Yes, GATE is required. / No, you do not qualify for exemption.
- 8.0 -> No, GATE is not required. / Yes, you qualify for exemption.
- 8.01 -> No, GATE is not required. / Yes, you qualify for exemption.

Never give a conclusion that contradicts the numerical comparison.

If the user asks whether they qualify but does not provide enough information:

State what information is missing instead of assuming.

Example:

Question:
Do I qualify for GATE exemption?

Answer:
The document states that IIT/CFTI graduates with a CGPA of 8.0 or above are exempt from GATE. Your CGPA and qualification are not provided.

REQUIREMENTS RULE

When answering questions about requirements, eligibility criteria, conditions, coursework, candidacy, thesis submission, or procedures:

- Preserve the complete requirement.
- Do not shorten important conditions.
- Include both the activity and its threshold.

Bad:
"Achieving a grade point of 7.00"

Good:
"Successful completion of the required coursework and seminar credits with a CGPA of at least 7.00."

ANSWER FORMAT

1. Simple factual questions
   (definitions, abbreviations, limits, numbers, thresholds, durations)

   Answer in 1 sentence.

Example:
Question:
What does SGPA stand for?

Answer:
SGPA stands for Semester Grade Point Average.

2. Eligibility questions

   Answer in 1-2 sentences.

Example:
Question:
I graduated from IIT with a CGPA of 7.99. Do I qualify for GATE exemption?

Answer:
No. The exemption requires a CGPA of 8.0 or above, and 7.99 does not meet this requirement.

3. Requirement or process questions

   Use concise bullet points.

Example:
Question:
What are the candidacy requirements?

Answer:
• Successful completion of required coursework and seminar credits with a CGPA of at least 7.00.
• Successful completion of the comprehensive examination.
• Approval of the research proposal by the SRC.

4. Compound questions

   Only if the user explicitly asks more than one question:
   - Identify each question.
   - Answer each separately.
   - Do not create additional sections.
   - Do not infer additional questions.

Example:

1. GATE Exemption:
No. The exemption requires a CGPA of 8.0 or above, and 7.99 does not meet this requirement.

2. Coursework:
Required coursework and seminar credits must be completed with a CGPA of at least 7.00.

GREETINGS

If the user sends only a greeting such as:
hi, hello, hey, hii, hiii, greetings

Respond with a short greeting and ask how you can help.

Do not use document context for greetings.

FINAL RULE

Give the shortest correct answer that fully satisfies the question while preserving all important conditions and thresholds.
"""

def ask(question, context_chunks):
    """Send a question with RAG context to the LLM.
    
    Args:
        question: User question string
        context_chunks: List of reranked dicts [{"chunk": "...", "page": 1, "rerank_score": ...}, ...]
    
    Returns:
        dict: {"answer": "...", "sources": [1, 3]}
    """
    # Handle deterministic CGPA comparison for GATE exemption queries
    import re
    cgpa_match = re.search(r'cgpa\s*(?:of|is)?\s*(\d+\.?\d*)', question.lower())
    if cgpa_match and any(word in question.lower() for word in ["gate", "exemption", "exempt"]):
        cgpa = float(cgpa_match.group(1))
        if cgpa >= 8.0:
            if any(phrase in question.lower() for phrase in ["need gate", "require gate", "gate required", "need a test", "require a test"]):
                answer = "No, you do not need GATE. Candidates with a Bachelor's or Master's degree from IITs/CFTIs with a CGPA of 8.0 or above are exempt from GATE."
            else:
                answer = "Yes, you qualify for GATE exemption. Candidates with a Bachelor's or Master's degree from IITs/CFTIs with a CGPA of 8.0 or above are exempt from GATE."
        else:
            if any(phrase in question.lower() for phrase in ["need gate", "require gate", "gate required", "need a test", "require a test"]):
                answer = f"Yes, you need GATE. The exemption requires a CGPA of 8.0 or above, and your CGPA of {cgpa} does not meet this requirement."
            else:
                answer = f"No, you do not qualify for GATE exemption. The exemption requires a CGPA of 8.0 or above, and your CGPA of {cgpa} does not meet this requirement."
        
        source_pages = list(set(c["page"] for c in context_chunks if c["page"] in [15, 16]))
        if not source_pages:
            source_pages = [15, 16]
        return {
            "answer": answer,
            "sources": source_pages
        }

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

    # Count how many questions the user asked
    question_count = question.count("?")
    if question_count <= 1:
        prompt += """

QUESTION COUNT RULE

Count how many questions the user asked.

If exactly one question is asked:
- Answer exactly that question.
- Do not create additional sections.
- Do not discuss admission eligibility, coursework, candidacy, thesis submission, or any other topic unless explicitly asked."""
    else:
        prompt += """

QUESTION COUNT RULE

Count how many questions the user asked.

If multiple questions are asked:
- Answer only those questions.
- Create one section per question."""

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
