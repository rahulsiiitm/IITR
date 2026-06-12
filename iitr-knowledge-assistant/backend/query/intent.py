import logging
import os
from transformers import pipeline

logger = logging.getLogger(__name__)

# Force CPU for the classifier to avoid CUDA OOM if running locally
os.environ["CUDA_VISIBLE_DEVICES"] = ""

class IntentRouter:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            logger.info("Loading Zero-Shot Intent Classifier...")
            cls._instance = super(IntentRouter, cls).__new__(cls)
            # Using a very fast, lightweight distilroberta-based NLI model (~320MB)
            cls._instance.classifier = pipeline(
                "zero-shot-classification",
                model="cross-encoder/nli-distilroberta-base",
                device=-1 # Force CPU
            )
            cls._instance.labels = [
                "academic question about university phd regulations, admissions, or thesis",
                "conversational, greeting, or asking for identity",
                "out of domain, weather, random, or unrelated to academics"
            ]
        return cls._instance

    def classify(self, question: str) -> str:
        """Classify the user's intent into predefined categories."""
        if len(question.strip()) < 2:
            return "out of domain"

        # ── Keyword guardrail: if the question mentions known regulatory topics,
        # always treat it as academic regardless of NLI classifier confidence.
        REGULATORY_KEYWORDS = {
            "candidacy", "candidate", "phd", "thesis", "dissertation",
            "cgpa", "sgpa", "grade", "coursework", "course", "credit",
            "admission", "admit", "apply", "application", "eligib",
            "gate", "exempt", "fellowship", "stipend", "scholarship",
            "supervisor", "guide", "advisor", "committee", "src", "drc",
            "irc", "daa", "comprehensive", "examination", "research proposal",
            "synopsis", "viva", "defense", "defence", "oral", "submission",
            "registration", "enroll", "semester", "regulation", "rule",
            "requirement", "duration", "period", "leave", "absence",
            "part-time", "full-time", "convert", "transfer", "progress",
            "annual review", "annual progress", "extension", "deadline",
        }
        q_lower = question.lower()
        if any(kw in q_lower for kw in REGULATORY_KEYWORDS):
            logger.info("Intent Router: keyword guardrail → academic")
            return "academic"

        result = self.classifier(question, self.labels)
        top_intent = result["labels"][0]
        confidence = result["scores"][0]
        
        logger.info(f"Intent Router: {top_intent} (Confidence: {confidence:.2f})")
        
        if "out of domain" in top_intent:
            return "out_of_domain"
        elif "conversational" in top_intent:
            return "conversational"
        else:
            return "academic"

# Global instance
intent_router = None

def get_intent_router():
    global intent_router
    if intent_router is None:
        intent_router = IntentRouter()
    return intent_router
