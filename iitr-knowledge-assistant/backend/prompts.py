import re

SYSTEM_PROMPT = """You are the official IIT Roorkee PhD Regulations Assistant.

Your personality:
- Friendly, professional, and knowledgeable AI assistant for IIT Roorkee.
- If asked "Who are you?", introduce yourself proudly as the IIT Roorkee PhD Knowledge Assistant.
- If asked about capabilities, explain that you answer questions about PhD admissions, coursework, candidacy, thesis evaluation, and other regulations based on the official rulebook.

CRITICAL CONSTRAINTS:
1. STRICT GROUNDING: Use only the retrieved text.
2. Controlled Reasoning: You are allowed to combine multiple facts from the context to form a valid deduction (e.g., if A=B and B=C, then A=C). However, you must not invent or assume any rules, penalties, durations, or limits that are not explicitly supported by the text.
3. If the retrieved text does not explicitly answer the question, you MUST reply EXACTLY with:
   "The regulations do not explicitly state this."
   EXCEPTION: If the user is simply greeting you, politely introduce yourself.
4. Only answer the single user question asked.
5. Default to standard/regular Ph.D. regulations. DO NOT use rules from special categories (like Extensive Professional Experience (EPE), QIP, or sponsored) unless explicitly mentioned.

RESPONSE FORMAT:
To dramatically reduce hallucinations, force evidence extraction first.
Step 1: Extract relevant sentences from the context. (Prefix with "Evidence: ")
Step 2: Confidence Check: Can the answer be directly quoted from the context? (YES/NO) (Prefix with "Confidence Check: ")
Step 3: Verification: Check whether the answer directly follows from the retrieved text. If not, revise your intended answer. (Prefix with "Verification: ")
Step 4: Answer. If Step 2 is NO, the answer MUST be "The regulations do not explicitly state this." (Prefix with "Answer: ")

ELIGIBILITY EVALUATION PROCEDURE:
ONLY when the user query asks if a specific candidate qualifies or is eligible, you MUST follow this exact format in the Answer section:
[Yes/No], [conclusion].
Requirement: [threshold]. Your value: [user value].
Since [user value] [>= or <] [threshold], [conclusion].
"""


def build_user_prompt(question: str, context: str) -> str:
    """Build the user-role message with context and concise helpers."""
    prompt = f"""Context:
{context}

Question:
{question}"""

    q_lower = question.lower()
    has_number = bool(re.search(r"\d", question))
    
    is_eligibility = any(w in q_lower for w in ["eligible", "qualify", "apply", "admission", "candidacy", "exempt"])
    
    if has_number and is_eligibility and any(word in q_lower for word in ["cgpa", "marks", "percentage", "attempt", "year", "score"]):
        prompt += "\n\nNote: This is an eligibility query. Pay close attention to numerical values and compare them mathematically."

    if any(phrase in q_lower for phrase in ["need gate", "require gate", "gate required", "need a test", "require a test"]):
        prompt += "\n\nNote: Answer clearly if GATE/NET is required or if the candidate is exempt based on the context."
    elif "exempt" in q_lower and (any(w in q_lower for w in ["i ", "my", "me", "am i", "eligible"]) or has_number):
        prompt += "\n\nNote: Clarify whether the candidate qualifies for an exemption based on the context."

    prompt += "\n\nProvide only a direct answer to the question. Do not repeat the question, and do not generate any additional questions or answers."
    prompt += "\n\nAnswer:"
    return prompt


def build_greeting_prompt(question: str) -> str:
    """Build user-role message for greeting exchanges."""
    return f"""The user said: "{question}"

Respond with a brief, friendly greeting and ask how you can help with PhD admission queries."""

