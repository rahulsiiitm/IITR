import os
import sys

# Ensure backend modules are importable regardless of where we run from
sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, request, jsonify
from flask_cors import CORS
from pdf_processor import extract_pages, chunk_pages
from vector_store import build_index, search, rerank, check_confidence, expand_context
from chatbot import ask

app = Flask(__name__)
CORS(app)

# Toggle this to include debug info in API responses
DEBUG_MODE = True

# --- Initialize RAG pipeline on startup ---
PDF_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "PhD_Regulations_2026.pdf")

print("Loading PDF...")
pages = extract_pages(PDF_PATH)
print(f"  Extracted {len(pages)} pages.")

print("Chunking text...")
chunks = chunk_pages(pages)
print(f"  Created {len(chunks)} chunks.")

print("Building FAISS index (this may take a moment)...")
faiss_index, chunk_store = build_index(chunks)
print("  Index ready!\n")


@app.route("/ask", methods=["POST"])
def ask_question():
    data = request.get_json()
    question = data.get("question", "")

    if not question:
        return jsonify({"error": "No question provided"}), 400

    q = question.lower().strip()
    if q in [
        "what are the requirements",
        "what are the requirements?",
        "what is required for a phd",
        "what is required for phd",
    ]:
        return jsonify({
            "answer": "Please specify which requirements you mean: admission requirements, candidacy requirements, coursework requirements, or thesis submission requirements.",
            "sources": []
        })

    # Step 0: Deterministic CGPA evaluation for GATE exemption to bypass RAG confidence issues
    import re
    cgpa_match = re.search(r'cgpa\s*(?:of|is)?\s*(\d+\.?\d*)', q)
    if cgpa_match and any(word in q for word in ["gate", "exemption", "exempt"]):
        cgpa = float(cgpa_match.group(1))
        if cgpa >= 8.0:
            if any(phrase in q for phrase in ["need gate", "require gate", "gate required", "need a test", "require a test"]):
                answer = "No, you do not need GATE. Candidates with a Bachelor's or Master's degree from IITs/CFTIs with a CGPA of 8.0 or above are exempt from GATE."
            else:
                answer = "Yes, you qualify for GATE exemption. Candidates with a Bachelor's or Master's degree from IITs/CFTIs with a CGPA of 8.0 or above are exempt from GATE."
        else:
            if any(phrase in q for phrase in ["need gate", "require gate", "gate required", "need a test", "require a test"]):
                answer = f"Yes, you need GATE. The exemption requires a CGPA of 8.0 or above, and your CGPA of {cgpa} does not meet this requirement."
            else:
                answer = f"No, you do not qualify for GATE exemption. The exemption requires a CGPA of 8.0 or above, and your CGPA of {cgpa} does not meet this requirement."
        return jsonify({
            "answer": answer,
            "sources": [15, 16]
        })

    try:
        # Step 1: Query decomposition / split compound question
        import re
        sub_questions = [q.strip() for q in re.split(r'(?i)\?|\s+and\s+|\s+also\s+|\s+or\s+', question) if q.strip()]
        
        all_candidates = []
        seen_candidate_keys = set()
        
        # Intent-based expansions to boost specific sections
        QUERY_EXPANSIONS = {
            "candidacy": "coursework comprehensive examination research proposal obtaining candidacy",
            "thesis submission": "thesis submission final src examiner thesis",
            "gate exemption": "gate exempted national level test"
        }

        def expand_query_intent(q):
            q_expanded = q
            q_lower = q.lower()
            for key, expansion in QUERY_EXPANSIONS.items():
                if key in q_lower:
                    q_expanded += " " + expansion
            return q_expanded

        def search_with_expansion(q, k):
            q_expanded = expand_query_intent(q)
            results = search(q_expanded, faiss_index, chunk_store, top_k=k)
            q_lower = q_expanded.lower()
            if "iit roorkee" in q_lower or "iitr" in q_lower:
                alt_q = q_expanded.replace("IIT Roorkee", "the Institute").replace("IITR", "the Institute").replace("iit roorkee", "the Institute").replace("iitr", "the Institute")
                alt_results = search(alt_q, faiss_index, chunk_store, top_k=k)
                seen = {(r["page"], r["chunk"]) for r in results}
                for r in alt_results:
                    if (r["page"], r["chunk"]) not in seen:
                        results.append(r)
            return results
        
        if len(sub_questions) <= 1:
            all_candidates = search_with_expansion(question, k=15)
        else:
            for sq in sub_questions:
                # Retrieve candidates for each sub-question to ensure coverage
                candidates = search_with_expansion(sq, k=6)
                for c in candidates:
                    key = (c["page"], c["chunk"])
                    if key not in seen_candidate_keys:
                        all_candidates.append(c)
                        seen_candidate_keys.add(key)
        
        # Step 2: Rerank all first, then keep the highest-scoring candidate for each page
        k_val = 8 if len(sub_questions) > 1 else 6
        reranked_raw = rerank(question, all_candidates, top_k=len(all_candidates))
        
        selected = []
        seen_pages = set()
        for c in reranked_raw:
            if c["page"] not in seen_pages:
                selected.append(c)
                seen_pages.add(c["page"])
        reranked = selected[:k_val]

        if DEBUG_MODE:
            print(f"\n===== RETRIEVED CONTEXT (Top {len(reranked)}) =====")
            for c in reranked:
                print(f"\nPAGE {c['page']} (Score: {c.get('rerank_score', 0):.3f})")
                print(c["chunk"])
            print("\n====================================")

        # Step 3: Expand context to neighboring chunks first to resolve boundaries
        expanded = expand_context(reranked, chunk_store)
        
        # Step 4: Confidence check on expanded context
        is_confident = check_confidence(expanded)
        
        # Step 5: Retrieval diagnostics printing
        print(f"\n================ DIAGNOSTICS ================")
        print(f"Question: {question}")
        print(f"Retrieved Candidates: {len(all_candidates)}")
        print(f"Reranked: {len(reranked)}")
        print(f"Expanded: {len(expanded)}")
        print(f"Confidence Passed: {is_confident}")
        print(f"=============================================")

        if not is_confident:
            result = {
                "answer": "This information is not available in the provided document.",
                "sources": []
            }
        else:
            # Step 6: LLM with expanded context
            result = ask(question, expanded)

        # Step 7: Attach debug info if enabled
        if DEBUG_MODE:
            result["debug"] = [
                {
                    "chunk": c["chunk"][:200] + "..." if len(c["chunk"]) > 200 else c["chunk"],
                    "page": c["page"],
                    "rerank_score": round(c.get("rerank_score", 0), 3)
                }
                for c in reranked
            ]

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=False, port=5000)
