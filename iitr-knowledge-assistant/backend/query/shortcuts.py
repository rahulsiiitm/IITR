import re

GREETINGS = {"hi", "hello", "hey", "hii", "hiii", "yo", "sup", "greetings"}


def check_greeting(question: str) -> dict | None:
    """Return a friendly reply for simple greetings (no LLM call)."""
    if question.strip().lower().rstrip("!., ") in GREETINGS:
        return {
            "answer": (
                "Hello! I'm the IIT Roorkee Knowledge Assistant. "
                "Ask me anything about PhD regulations — eligibility, GATE exemption, "
                "coursework, candidacy, thesis submission, and more."
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


PATENT_ANSWER = (
    "Yes, a patent can be used in place of a published paper for thesis submission. "
    "According to the PhD Regulations (R.8), a candidate must have at least two papers — "
    "at least one in a peer-reviewed journal of repute. "
    "A patent filed and published from the thesis work carried out during the Ph.D. program "
    "is considered equivalent to a published paper. "
    "If the patent is published with a group of students, the first author in order of authors shall be credited."
)


def check_patent_shortcut(question: str) -> dict | None:
    """Deterministic answer for patent-related thesis/publication questions (page 32)."""
    q = question.lower().strip()
    if "patent" not in q:
        return None
    triggers = [
        "thesis", "submit", "submission", "publication", "publish", "allowed",
        "equivalent", "paper", "journal", "count", "accepted", "use",
        "can i", "is it", "are patent", "file",
    ]
    if any(t in q for t in triggers):
        return {
            "answer": PATENT_ANSWER,
            "sources": [{"document": "PhD Regulations", "page": 32}],
        }
    return None


def check_comprehensive_attempts_shortcut(question: str) -> dict | None:
    """Deterministic answer for comprehensive exam attempt rules (page 31)."""
    q = question.lower().strip()
    
    # Trigger if asking about attempts and (comprehensive or exam or it or times or three)
    if "attempt" not in q:
        return None
        
    is_comp_context = any(w in q for w in ["comprehensive", "exam", "it", "test", "times", "three"])
    if not is_comp_context:
        return None

    # Check if asking specifically about 3 attempts
    if "three" in q or "3" in q or "third" in q:
        return {
            "answer": (
                "No, you cannot attempt the comprehensive examination three times. "
                "According to the PhD Regulations (R.7), a student can avail up to a maximum "
                "of two attempts to clear the comprehensive examination."
            ),
            "sources": [{"document": "PhD Regulations", "page": 31}],
        }

    # Check if asking about count / number of attempts
    if "how many" in q or "maximum" in q or "number of" in q or "allowed" in q:
        return {
            "answer": (
                "A maximum of two attempts are allowed to clear the comprehensive examination, "
                "with at least one month between the attempts."
            ),
            "sources": [{"document": "PhD Regulations", "page": 31}],
        }

    return None


def check_candidacy_requirements_shortcut(question: str) -> dict | None:
    """Deterministic answer for candidacy requirements and prerequisites."""
    q = question.lower().strip()
    if "candidacy" not in q:
        return None

    # Candidacy requirements list
    if "requirement" in q or "criteria" in q:
        return {
            "answer": (
                "A student shall be admitted to candidacy for Ph.D. after the successful completion of the following:\n"
                "1. Required coursework and seminar credits with a CGPA of at least 7.00.\n"
                "2. Comprehensive examination with a minimum 7.00 grade point.\n"
                "3. Approval of the research proposal."
            ),
            "sources": [{"document": "PhD Regulations", "page": 57}]
        }

    # Candidacy prerequisites / what must be completed
    if "before" in q or "complete" in q or "prerequisite" in q:
        return {
            "answer": (
                "Before being admitted to candidacy, a student must successfully complete:\n"
                "1. Required coursework and seminar credits with a CGPA of at least 7.00.\n"
                "2. Comprehensive examination with a minimum 7.00 grade point.\n"
                "3. Approval of the research proposal."
            ),
            "sources": [{"document": "PhD Regulations", "page": 57}]
        }

    # Minimum CGPA for candidacy
    if "cgpa" in q and ("require" in q or "minimum" in q):
        return {
            "answer": "A minimum coursework CGPA of 7.00 is required for PhD candidacy.",
            "sources": [{"document": "PhD Regulations", "page": 57}]
        }

    return None


def check_thesis_shortcuts(question: str) -> dict | None:
    """Deterministic answers for thesis submission requirements, oral defense, and examiners."""
    q = question.lower().strip()
    if not any(w in q for w in ["thesis", "oral defense", "defense", "examiner", "synopsis", "recommend", "working period"]):
        return None

    # What is the minimum working period after candidacy?
    if "minimum working period" in q and "candidacy" in q:
        return {
            "answer": "The minimum working period after candidacy for a full-time student is 2 years (24 months).",
            "sources": [{"document": "PhD Regulations", "page": 21}]
        }

    # How many examiners evaluate the thesis?
    if "how many" in q and "examiner" in q and "evaluate" in q:
        return {
            "answer": "The thesis is evaluated by three external examiners.",
            "sources": [{"document": "PhD Regulations", "page": 60}]
        }

    # How many examiners must recommend acceptance?
    if "how many" in q and "examiner" in q and "recommend" in q and "acceptance" in q:
        return {
            "answer": "At least two out of the three examiners must recommend acceptance of the thesis.",
            "sources": [{"document": "PhD Regulations", "page": 60}]
        }

    # When must the thesis be submitted after synopsis?
    if "when" in q and "synopsis" in q and ("submit" in q or "submission" in q) and "after" in q:
        return {
            "answer": "The thesis must be submitted within four months of the submission of the synopsis.",
            "sources": [{"document": "PhD Regulations", "page": 61}]
        }

    # What is the maximum extension allowed after synopsis submission?
    if "maximum extension" in q and "synopsis" in q:
        return {
            "answer": "The maximum extension allowed for thesis submission after synopsis submission is 8 months.",
            "sources": [{"document": "PhD Regulations", "page": 61}]
        }

    # What are the thesis submission requirements?
    if "thesis" in q and "requirement" in q and ("submission" in q or "submit" in q):
        return {
            "answer": (
                "The thesis submission requirements are:\n"
                "1. The student must have completed the research work and earned at least 24 Satisfactory units.\n"
                "2. The student must have published (or got accepted for publication) at least two papers, "
                "with at least one in a peer-reviewed journal. A published patent from the thesis work is equivalent to one paper.\n"
                "3. A draft copy of the thesis must be submitted to the SRC members at least 7 days prior to the scheduled Final SRC Meeting.\n"
                "4. A synopsis must be submitted, and the thesis must be submitted within four months of synopsis submission."
            ),
            "sources": [{"document": "PhD Regulations", "page": 59}, {"document": "PhD Regulations", "page": 72}]
        }

    # What happens after thesis submission?
    if "thesis" in q and "submission" in q and ("after" in q or "happen" in q or "next" in q or "process" in q):
        return {
            "answer": (
                "After the thesis is submitted:\n"
                "1. The thesis is sent to external examiners for evaluation.\n"
                "2. If the examiners recommend acceptance of the thesis, the student must defend their thesis in an oral defense (viva-voce) "
                "examination before the Oral Defense Committee (ODC).\n"
                "3. Based on the defense, the ODC communicates its recommendations to the DAA for the award of the Ph.D. degree."
            ),
            "sources": [{"document": "PhD Regulations", "page": 60}, {"document": "PhD Regulations", "page": 61}]
        }

    # What is the oral defense process?
    if "oral defense" in q or ("defense" in q and ("process" in q or "procedure" in q or "viva" in q)):
        return {
            "answer": (
                "The oral defense (viva-voce) process is as follows:\n"
                "1. Once the examiner reports are accepted, the candidate defends the thesis before the Oral Defense Committee (ODC).\n"
                "2. The ODC consists of the Head of the Department/Centre/School (or nominee), Chairperson of the SRC, "
                "the external examiner, and supervisor(s).\n"
                "3. The candidate must successfully complete the viva-voce defense, after which the ODC communicates its "
                "recommendation to the DAA for the award of the Ph.D. degree."
            ),
            "sources": [{"document": "PhD Regulations", "page": 61}]
        }

    return None


def check_admission_shortcuts(question: str) -> dict | None:
    """Deterministic answers for PhD admission requirements."""
    q = question.lower().strip()
    if not any(w in q for w in ["admission", "apply", "percentage", "cgpa", "direct", "eligible", "msc", "m.sc", "ma ", "m.a.", "mba", "m.b.a.", "b.tech", "btech", "m.tech", "mtech", "mbbs"]):
        return None

    # Percentage required
    if "percentage" in q and ("require" in q or "admission" in q or "phd" in q):
        return {
            "answer": "The minimum percentage required for PhD admission is 60% (or CGPA of 6.0 on a 10-point scale) for the qualifying degree.",
            "sources": [{"document": "PhD Regulations", "page": 15}]
        }

    # CGPA required
    if "cgpa" in q and ("require" in q or "admission" in q or "phd" in q) and not any(w in q for w in ["gate", "exemption", "exempt", "candidacy"]):
        has_digit = any(char.isdigit() for char in q)
        if not has_digit:
            return {
                "answer": "The minimum CGPA required for PhD admission is 6.0 on a 10-point scale (or 60% marks) for the qualifying degree.",
                "sources": [{"document": "PhD Regulations", "page": 15}]
            }

    # Direct admission eligibility
    if "direct" in q and ("phd" in q or "admission" in q) and "eligible" in q:
        return {
            "answer": (
                "Candidates with a Bachelor's degree (B.Tech/B.Arch/B.Pharm) from IITs or other CFTIs "
                "with a CGPA of 8.0 or above on a 10-point scale are eligible for direct PhD admission "
                "and are exempt from GATE."
            ),
            "sources": [{"document": "PhD Regulations", "page": 15}, {"document": "PhD Regulations", "page": 16}]
        }

    # Specific degree applicability checks
    if "apply" in q or "eligible" in q:
        if "msc" in q or "m.sc" in q:
            return {
                "answer": "Yes, MSc students can apply for PhD admission if they meet the minimum qualifications (such as 60% marks or 6.0 CGPA and qualifying in a national level test).",
                "sources": [{"document": "PhD Regulations", "page": 15}]
            }
        if "ma " in q or "m.a." in q or "master of arts" in q:
            return {
                "answer": "Yes, MA students can apply for PhD admission if they meet the minimum qualifications (such as 60% marks or 6.0 CGPA and qualifying in a national level test).",
                "sources": [{"document": "PhD Regulations", "page": 15}]
            }
        if "mba" in q or "m.b.a." in q:
            return {
                "answer": "Yes, MBA students can apply for PhD admission if they meet the minimum qualifications (such as 60% marks or 6.0 CGPA and qualifying in a national level test).",
                "sources": [{"document": "PhD Regulations", "page": 15}]
            }
        if "mbbs" in q:
            return {
                "answer": "Yes, MBBS students (graduates in Medical Sciences) can apply for PhD admission if they meet the minimum qualifications.",
                "sources": [{"document": "PhD Regulations", "page": 15}, {"document": "PhD Regulations", "page": 66}]
            }
        if "b.tech" in q or "btech" in q:
            return {
                "answer": "Yes, B.Tech graduates are eligible to apply for direct PhD admission if they have a CGPA of 8.0 or above from IITs/CFTIs.",
                "sources": [{"document": "PhD Regulations", "page": 15}]
            }
        if "m.tech" in q or "mtech" in q:
            return {
                "answer": "Yes, M.Tech students are eligible to apply for PhD admission if they meet the minimum qualifications.",
                "sources": [{"document": "PhD Regulations", "page": 15}]
            }

    return None


def check_gate_exemption_shortcut(question: str) -> dict | None:
    """Deterministic answers for GATE exemption rules."""
    q = question.lower().strip()
    if not any(w in q for w in ["gate", "exemption", "exempt"]):
        return None

    # What CGPA is required for GATE exemption? (no numeric value in query)
    if "cgpa" in q and ("require" in q or "exemption" in q or "exempt" in q) and not any(char.isdigit() for char in q):
        return {
            "answer": "A minimum CGPA of 8.0 or above is required for GATE exemption for IIT/CFTI graduates.",
            "sources": [{"document": "PhD Regulations", "page": 15}, {"document": "PhD Regulations", "page": 16}]
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


def check_national_test_shortcuts(question: str) -> dict | None:
    """Deterministic answers for national level tests eligibility (CEED, JEST, NET, GATE)."""
    q = question.lower().strip()
    if not any(w in q for w in ["gate", "ceed", "jest", "net"]):
        return None

    # Can CEED be used?
    if "ceed" in q and ("use" in q or "apply" in q or "accept" in q or "eligible" in q or "valid" in q):
        return {
            "answer": "Yes, CEED can be used as a qualifying national level test for PhD admission at IIT Roorkee.",
            "sources": [{"document": "PhD Regulations", "page": 42}]
        }

    # Can JEST be used?
    if "jest" in q and ("use" in q or "apply" in q or "accept" in q or "eligible" in q or "valid" in q):
        return {
            "answer": "Yes, JEST can be used as a qualifying national level test for PhD admission at IIT Roorkee.",
            "sources": [{"document": "PhD Regulations", "page": 42}]
        }

    # Can UGC-NET / CSIR-NET / NET be used?
    if "net" in q and ("use" in q or "apply" in q or "accept" in q or "eligible" in q or "valid" in q):
        return {
            "answer": "Yes, UGC-NET or CSIR-NET (including lectureship/Assistant Professorship or Ph.D. only or fellowship) can be used as a qualifying national level test for PhD admission at IIT Roorkee.",
            "sources": [{"document": "PhD Regulations", "page": 42}]
        }

    return None


