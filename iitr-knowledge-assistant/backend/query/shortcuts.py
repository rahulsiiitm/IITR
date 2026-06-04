import re


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
    cgpa_match = re.search(r"cgpa\s*(?:of|is)?\s*(\d+\.?\d*)", q)
    if not cgpa_match or not any(word in q for word in ["gate", "exemption", "exempt"]):
        return None

    cgpa = float(cgpa_match.group(1))
    need_gate_phrases = [
        "need gate",
        "require gate",
        "gate required",
        "need a test",
        "require a test",
    ]

    if cgpa >= 8.0:
        if any(phrase in q for phrase in need_gate_phrases):
            answer = (
                "No, you do not need GATE. Candidates with a Bachelor's or Master's "
                "degree from IITs/CFTIs with a CGPA of 8.0 or above are exempt from GATE."
            )
        else:
            answer = (
                "Yes, you qualify for GATE exemption. Candidates with a Bachelor's or "
                "Master's degree from IITs/CFTIs with a CGPA of 8.0 or above are exempt from GATE."
            )
    else:
        if any(phrase in q for phrase in need_gate_phrases):
            answer = (
                f"Yes, you need GATE. The exemption requires a CGPA of 8.0 or above, "
                f"and your CGPA of {cgpa} does not meet this requirement."
            )
        else:
            answer = (
                f"No, you do not qualify for GATE exemption. The exemption requires a CGPA "
                f"of 8.0 or above, and your CGPA of {cgpa} does not meet this requirement."
            )

    return {
        "answer": answer,
        "sources": [{"document": "PhD Regulations", "page": p} for p in [15, 16]],
    }
