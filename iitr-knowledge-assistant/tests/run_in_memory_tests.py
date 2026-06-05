import os
import sys
import json
import time
from pathlib import Path
from fastapi.testclient import TestClient

PROJECT_ROOT = Path("/home/rahul/Projects/Summer 2026 Stuff/IITR/iitr-knowledge-assistant")
sys.path.insert(0, str(PROJECT_ROOT))

# Force CPU execution to prevent CUDA OOM
os.environ["CUDA_VISIBLE_DEVICES"] = ""

from backend.main import app

def main():
    test_files = {
        "admission": "tests/admission.json",
        "gate": "tests/gate.json",
        "candidacy": "tests/candidacy.json",
        "thesis": "tests/thesis.json",
        "hallucination": "tests/hallucination.json"
    }

    results = []
    
    total_non_hallucination = 0
    passed_non_hallucination = 0
    total_hallucination = 0
    failed_hallucination_rejection = 0 # meaning it hallucinated (did not say N/A)

    print("=" * 70)
    print(" IIT ROORKEE PHD KNOWLEDGE ASSISTANT - IN-MEMORY REGRESSION TESTS")
    print("=" * 70)

    # Wrap inside TestClient context manager to trigger lifespan startup (loads FAISS/BM25)
    with TestClient(app) as client:
        for category, path in test_files.items():
            if not os.path.exists(path):
                print(f"Test file not found: {path}")
                continue

            print(f"\n--- Running category: {category.upper()} ---")
            with open(path) as f:
                test_cases = json.load(f)

            for idx, case in enumerate(test_cases, 1):
                q = case["question"]
                expect_type = case["expect_type"]
                must_contain = case.get("must_contain", [])
                must_not_contain = case.get("must_not_contain", [])

                # Query FastAPI in-memory
                start_time = time.time()
                headers = {"X-API-Key": "dev_key_123"}
                response = client.post("/ask", json={"question": q}, headers=headers)
                latency = time.time() - start_time
                
                ans = response.json().get("answer", "")
                ans_lower = ans.lower()

                is_na = "information is not available" in ans_lower or ans_lower.startswith("information not available")

                passed = False
                fail_reason = ""

                if expect_type == "unavailable":
                    total_hallucination += 1
                    if is_na:
                        passed = True
                    else:
                        passed = False
                        failed_hallucination_rejection += 1
                        fail_reason = "Expected query rejection but got response (hallucination risk)"
                else:
                    total_non_hallucination += 1
                    if is_na:
                        passed = False
                        fail_reason = "Factual answer expected but got 'Information not available'"
                    else:
                        def match_term(term: str, text: str) -> bool:
                            t_lower = term.lower().strip()
                            if t_lower == "m.sc" or t_lower == "msc":
                                return "msc" in text.replace(".", "")
                            
                            equivalents = {
                                "three": ["three", "3"],
                                "3": ["three", "3"],
                                "two": ["two", "2"],
                                "2": ["two", "2"],
                                "defense": ["defense", "defence"],
                                "defence": ["defense", "defence"],
                                "oral defense committee": ["oral defense committee", "oral defence committee"]
                            }
                            candidates = equivalents.get(t_lower, [t_lower])
                            return any(c in text for c in candidates)

                        # Check must contain conditions
                        missing = [p for p in must_contain if not match_term(p, ans_lower)]
                        # Check must not contain conditions
                        found_forbidden = [p for p in must_not_contain if p.lower() in ans_lower]

                        if missing:
                            fail_reason = f"Missing required terms: {missing}"
                        elif found_forbidden:
                            fail_reason = f"Contains forbidden terms: {found_forbidden}"
                        else:
                            passed = True
                            passed_non_hallucination += 1

                status_str = "\033[92mPASS\033[0m" if passed else "\033[91mFAIL\033[0m"
                print(f"[{idx}] Q: {q}")
                print(f"    Status: {status_str} (latency: {latency:.2f}s)")
                if not passed:
                    print(f"    Reason: {fail_reason}")
                    print(f"    Got: {ans}")

                results.append({
                    "category": category,
                    "question": q,
                    "passed": passed,
                    "latency": latency,
                    "reason": fail_reason,
                    "answer": ans
                })

    # Calculations
    accuracy = (passed_non_hallucination / total_non_hallucination * 100) if total_non_hallucination > 0 else 100.0
    hallucination_rate = (failed_hallucination_rejection / total_hallucination * 100) if total_hallucination > 0 else 0.0

    print("\n" + "=" * 70)
    print(" SUMMARY STATISTICS")
    print("=" * 70)
    print(f"Accuracy: {accuracy:.1f}%")
    print(f"Hallucination Rate: {hallucination_rate:.1f}%")
    print(f"Total Tests Run: {len(results)}")
    print(f"Factual queries passed: {passed_non_hallucination}/{total_non_hallucination}")
    print(f"Hallucination blocks succeeded: {total_hallucination - failed_hallucination_rejection}/{total_hallucination}")
    print("=" * 70)

    # Exit code based on any failures
    any_failures = any(not r["passed"] for r in results)
    if any_failures:
        print("\033[91mSome tests failed. Correct the failures before committing changes.\033[0m")
        sys.exit(1)
    else:
        print("\033[92mAll tests passed successfully! Perfect score.\033[0m")
        sys.exit(0)

if __name__ == "__main__":
    main()
