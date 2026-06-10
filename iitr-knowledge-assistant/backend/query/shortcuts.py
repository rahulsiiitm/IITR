import re

GREETINGS = {"hi", "hello", "hey", "hii", "hiii", "yo", "sup", "greetings"}


def check_greeting(question: str) -> dict | None:
    """Return a friendly reply for simple greetings or identity questions."""
    q_lower = question.strip().lower().rstrip("!., ?")
    
    # Catch basic greetings including 'hey', 'hello', etc.
    if re.match(r"^(hi+|hello+|hey+|yo|sup|greetings)( there)?$", q_lower):
        return {
            "answer": (
                "Hello! I'm Sutra, the official IIT Roorkee PhD Regulations Assistant. "
                "I can answer questions about PhD admissions, coursework, candidacy, "
                "thesis evaluation, and other academic regulations based on the rulebook."
            ),
            "sources": [],
        }
        
    # Catch variations of "who are you" / "what are you"
    if re.match(r"^(who|what)\s+(are|r)\s+(you|u)(.*)?$", q_lower) or re.match(r"^(introduce|tell me about)\s+(yourself|urself)(.*)?$", q_lower):
        return {
            "answer": (
                "I am Sutra, the official IIT Roorkee PhD Regulations Assistant. "
                "I am an AI trained specifically on the IIT Roorkee PhD Regulations rulebook. "
                "I can help you understand admission requirements, GATE exemptions, coursework, "
                "candidacy rules, and the complete thesis evaluation process."
            ),
            "sources": [],
        }
        
    return None


VAGUE_REQUIREMENTS = {
    "what are the requirements",
    "what are the requirements?",
    "what is required for a phd",
    "what is required for phd",
}


def check_vague_requirements(question: str) -> str | None:
    """Return disambiguation message for vague requirement questions."""
    if question.lower().strip() in VAGUE_REQUIREMENTS:
        return (
            "Please specify which requirements you mean: admission requirements, "
            "candidacy requirements, coursework requirements, or thesis submission requirements."
        )
    return None


def check_cgpa_gate_shortcut(question: str) -> dict | None:
    """Deterministic CGPA/GATE exemption answer when numeric CGPA is present."""
    q = question.lower().strip()
    # Match CGPA values from phrases like "cgpa 7.99", "cgpa of 7.99", or "cgpa 7.999"
    cgpa_match = re.search(r"cgpa\s*(?:of|is)?\s*(\d+\.?\d*)", q)
    if not cgpa_match or not any(word in q for word in ["gate", "exemption", "exempt"]):
        return None

    cgpa = float(cgpa_match.group(1))
    GATE_THRESHOLD = 8.0
    need_gate_phrases = [
        "need gate",
        "require gate",
        "gate required",
        "need a test",
        "require a test",
        "do i need",
    ]

    is_exempt = cgpa >= GATE_THRESHOLD
    is_asking_need = any(phrase in q for phrase in need_gate_phrases)

    if is_exempt:
        if is_asking_need:
            answer = (
                f"No, you do not need GATE. "
                f"Requirement: CGPA >= {GATE_THRESHOLD}. Your CGPA: {cgpa}. "
                f"Since {cgpa} >= {GATE_THRESHOLD}, you are exempt from GATE."
            )
        else:
            answer = (
                f"Yes, you qualify for GATE exemption. "
                f"Requirement: CGPA >= {GATE_THRESHOLD}. Your CGPA: {cgpa}. "
                f"Since {cgpa} >= {GATE_THRESHOLD}, you are exempt."
            )
    else:
        if is_asking_need:
            answer = (
                f"Yes, you need GATE. "
                f"Requirement: CGPA >= {GATE_THRESHOLD}. Your CGPA: {cgpa}. "
                f"Since {cgpa} < {GATE_THRESHOLD}, you do not qualify for exemption."
            )
        else:
            answer = (
                f"No, you do not qualify for GATE exemption. "
                f"Requirement: CGPA >= {GATE_THRESHOLD}. Your CGPA: {cgpa}. "
                f"Since {cgpa} < {GATE_THRESHOLD}, you do not meet the threshold."
            )

    return {
        "answer": answer,
        "sources": [{"document": "PhD Regulations", "page": p} for p in [15, 16]],
    }


def check_candidacy_cgpa_shortcut(question: str) -> dict | None:
    """Deterministic candidacy CGPA eligibility using pure Python arithmetic.

    Triggers only when the user provides a specific CGPA value AND asks about
    candidacy eligibility. Returns None if no personal value is provided (so the
    LLM can return the threshold directly).
    """
    q = question.lower().strip()
    # Must be a candidacy question
    if not any(word in q for word in ["candidacy", "candidate"]):
        return None

    # Must be an eligibility/personal question, not a threshold lookup
    is_personal = any(
        phrase in q
        for phrase in [
            "i have", "i've", "my cgpa", "cgpa is", "cgpa of",
            "am i eligible", "am i", "do i qualify", "can i",
        ]
    )
    if not is_personal:
        return None

    cgpa_match = re.search(r"cgpa\s*(?:of|is)?\s*(\d+\.?\d*)", q)
    if not cgpa_match:
        return None

    cgpa = float(cgpa_match.group(1))
    CANDIDACY_THRESHOLD = 7.0

    is_eligible = cgpa >= CANDIDACY_THRESHOLD

    if is_eligible:
        answer = (
            f"Yes, you are eligible for candidacy. "
            f"Requirement: CGPA >= {CANDIDACY_THRESHOLD}. Your CGPA: {cgpa}. "
            f"Since {cgpa} >= {CANDIDACY_THRESHOLD}, the coursework CGPA requirement is met. "
            f"You must also pass the comprehensive examination and get your research proposal approved."
        )
    else:
        answer = (
            f"No, you are not eligible for candidacy. "
            f"Requirement: CGPA >= {CANDIDACY_THRESHOLD}. Your CGPA: {cgpa}. "
            f"Since {cgpa} < {CANDIDACY_THRESHOLD}, you do not meet the minimum CGPA requirement."
        )

    return {
        "answer": answer,
        "sources": [{"document": "PhD Regulations", "page": p} for p in [29, 30]],
    }


ACRONYMS = {
    "ada": ("Associate Dean, Admission & IT Systems", 8),
    "adc": ("Associate Dean, Curriculum", 8),
    "ade": ("Associate Dean, Evaluation", 8),
    "cfc": ("Faculty Committee of the Centre", 8),
    "cgpa": ("Cumulative Grade Point Average", 8),
    "crc": ("the Research Committee of the Centre (Centre Research Committee)", 8),
    "daa": ("the Dean of Academic Affairs", 8),
    "dfc": ("Departmental Faculty Committee", 8),
    "dosw": ("the Dean of Students' Welfare", 9),
    "drc": ("Departmental Research Committee", 9),
    "irc": ("Research Committee of the Institute", 9),
    "odc": ("Oral Defence Committee", 10),
    "src": ("Student's Research Committee", 10),
    "scfc": ("Faculty Committee of the School", 9),
    "sgpa": ("Semester Grade Point Average", 9),
    "scrc": ("the Research Committee of the School", 10),
}


def check_acronym_shortcut(question: str) -> dict | None:
    """Deterministic acronym definition lookup when the user asks for standard abbreviations."""
    q = question.lower().strip().rstrip("?!.").strip()
    words = [w for w in q.split() if w not in {"a", "an", "the"}]
    if not words:
        return None

    target_acronym = None
    if len(words) == 1 and words[0] in ACRONYMS:
        target_acronym = words[0]
    elif len(words) >= 2 and words[0] == "what" and words[1] == "is" and words[-1] in ACRONYMS:
        # Only match if the intermediate words are simple fillers like "the meaning of", "full form of"
        fillers = {"the", "meaning", "of", "definition", "abbreviation", "full", "form"}
        in_between = [w for w in words[2:-1] if w not in fillers]
        if not in_between:
            target_acronym = words[-1]
    elif len(words) >= 4 and words[0] == "what" and words[1] == "does" and words[-1] == "for" and words[-2] == "stand" and words[-3] in ACRONYMS:
        target_acronym = words[-3]
    elif len(words) == 2 and words[0] in {"define", "meaning", "definition"} and words[1] in ACRONYMS:
        target_acronym = words[1]

    if target_acronym:
        definition, page = ACRONYMS[target_acronym]
        acronym_upper = target_acronym.upper()
        if target_acronym == "scrc":
            acronym_upper = "ScRC"
        elif target_acronym == "scfc":
            acronym_upper = "ScFC"

        return {
            "answer": f"{acronym_upper} stands for {definition}.",
            "sources": [{"document": "PhD Regulations", "page": page}]
        }
    return None


def check_admission_numerical_shortcut(question: str) -> dict | None:
    """Deterministic admission checks for specific percentage/CGPA values (page 15)."""
    q = question.lower().strip()
    
    # Check if asking about applying / eligibility / admission
    if not any(w in q for w in ["apply", "eligible", "admission", "qualify", "can a", "can i"]):
        return None

    # Do not conflict with candidacy or GATE exemption
    if any(w in q for w in ["candidacy", "gate", "exemption", "exempt"]):
        return None

    # Check percentage pattern
    pct_match = re.search(r"(\d+\.?\d*)\s*%", q)
    if pct_match:
        val = float(pct_match.group(1))
        MIN_PCT = 60.0
        is_eligible = val >= MIN_PCT
        if is_eligible:
            ans = f"Yes, a candidate with {val}% marks can apply. The minimum percentage required for PhD admission is 60%."
        else:
            ans = f"No, a candidate with {val}% marks cannot apply. The minimum percentage required for PhD admission is 60%."
        return {
            "answer": ans,
            "sources": [{"document": "PhD Regulations", "page": 15}]
        }

    # Check CGPA pattern
    cgpa_match = re.search(r"cgpa\s*(?:of|is)?\s*(\d+\.?\d*)", q)
    if cgpa_match:
        val = float(cgpa_match.group(1))
        MIN_CGPA = 6.0
        is_eligible = val >= MIN_CGPA
        if is_eligible:
            ans = f"Yes, a candidate with CGPA {val} can apply. The minimum CGPA required for PhD admission is 6.0 on a 10-point scale."
        else:
            ans = f"No, a candidate with CGPA {val} cannot apply. The minimum CGPA required for PhD admission is 6.0 on a 10-point scale."
        return {
            "answer": ans,
            "sources": [{"document": "PhD Regulations", "page": 15}]
        }

    return None


def check_phd_duration_shortcut(question: str) -> dict | None:
    """Deterministic answer for simple duration questions that confuse semantic search."""
    q = question.lower().strip().rstrip("?!.")
    duration_queries = {
        "minimum duration",
        "duration",
        "what is the minimum duration",
        "what is the minimum duration for a phd",
        "phd duration",
        "how long is a phd",
        "how long does a phd take",
        "minimum duration required",
        "minimum duration required for a phd"
    }
    if q in duration_queries:
        return {
            "answer": (
                "The minimum working period for the submission of a thesis for a full-time Ph.D. student is two years from the date of candidacy. "
                "For a part-time student, the minimum working period is three years from the date of candidacy. "
                "The maximum period for submission is five years for full-time students, and six years for part-time students from the date of initial registration."
            ),
            "sources": [{"document": "PhD Regulations", "page": 34}],
        }
    return None
