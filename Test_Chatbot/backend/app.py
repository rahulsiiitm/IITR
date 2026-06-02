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

    try:
        # Step 1: Query decomposition / split compound question
        import re
        sub_questions = [q.strip() for q in re.split(r'(?<=[.!?])\s+', question) if q.strip()]
        
        all_candidates = []
        seen_candidate_keys = set()
        
        def search_with_expansion(q, k):
            results = search(q, faiss_index, chunk_store, top_k=k)
            q_lower = q.lower()
            if "iit roorkee" in q_lower or "iitr" in q_lower:
                alt_q = q.replace("IIT Roorkee", "the Institute").replace("IITR", "the Institute").replace("iit roorkee", "the Institute").replace("iitr", "the Institute")
                alt_results = search(alt_q, faiss_index, chunk_store, top_k=k)
                seen = {r["chunk"] for r in results}
                for r in alt_results:
                    if r["chunk"] not in seen:
                        results.append(r)
            return results
        
        if len(sub_questions) <= 1:
            all_candidates = search_with_expansion(question, k=8)
        else:
            for sq in sub_questions:
                # Retrieve candidates for each sub-question to ensure coverage
                candidates = search_with_expansion(sq, k=4)
                for c in candidates:
                    key = c["chunk"]
                    if key not in seen_candidate_keys:
                        all_candidates.append(c)
                        seen_candidate_keys.add(key)
        
        # Step 2: Rerank to top 6 or 8
        k_val = 8 if len(sub_questions) > 1 else 6
        reranked = rerank(question, all_candidates, top_k=k_val)

        if DEBUG_MODE:
            print(f"\n===== RETRIEVED CONTEXT (Top {len(reranked)}) =====")
            for c in reranked:
                print(f"\nPAGE {c['page']} (Score: {c.get('rerank_score', 0):.3f})")
                print(c["chunk"])
            print("\n====================================")

        # Step 3: Confidence check
        if not check_confidence(reranked):
            result = {
                "answer": "This information is not available in the provided document.",
                "sources": []
            }
        else:
            # Expand context to neighboring chunks to fix boundaries
            expanded = expand_context(reranked, chunk_store)
            
            # Step 4: LLM with expanded context
            result = ask(question, expanded)

        # Step 5: Attach debug info if enabled
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
