import json
import re

with open("tests/raw_tests.txt", "r") as f:
    lines = f.readlines()

categories = {}
current_category = None

for line in lines:
    line = line.strip()
    if not line or line.startswith("Boundary") or line.startswith("These are") or line.startswith("If present") or line.startswith("Expected:"):
        continue
    
    if re.match(r"^\d+\.\s", line):
        current_category = re.sub(r"^\d+\.\s", "", line).strip().lower().replace(" ", "_").replace("/", "_")
        categories[current_category] = []
        continue

    if current_category:
        q = line
        
        # Simple heuristics for expect_type and must_contain
        expect_type = "answer"
        must_contain = []
        
        # Determine some basic ground truths
        if current_category == "hallucination_tests":
            expect_type = "unavailable"
            
        elif current_category == "numerical_boundary_tests":
            q = f"Can I apply with {line}?"
            val = float(line.replace("%", ""))
            if "%" in line:
                must_contain = ["yes"] if val >= 60 else ["no"]
            else:
                must_contain = ["yes"] if val >= 6.0 else ["no"]
        else:
            q_lower = q.lower()
            if "can i apply with 59" in q_lower or "5.99" in q_lower:
                must_contain = ["no"]
            elif "can i apply with 60" in q_lower or "6.0" in q_lower:
                must_contain = ["yes"]
            elif "gate exemption" in q_lower and "cgpa" in q_lower:
                must_contain = ["8.0"]
            elif "7.99" in q_lower:
                must_contain = ["no"]
            elif "8.0" in q_lower:
                must_contain = ["yes"]
                
        categories[current_category].append({
            "question": q,
            "expect_type": expect_type,
            "must_contain": must_contain
        })

for cat, tests in categories.items():
    if not tests: continue
    filepath = f"tests/{cat}.json"
    with open(filepath, "w") as f:
        json.dump(tests, f, indent=2)

print("Test files generated:", list(categories.keys()))
