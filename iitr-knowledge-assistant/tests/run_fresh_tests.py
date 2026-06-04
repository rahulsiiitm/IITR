import os
import sys
import time
import subprocess
import requests
from pathlib import Path

PROJECT_ROOT = Path("/home/rahul/Projects/Summer 2026 Stuff/IITR/iitr-knowledge-assistant")
sys.path.insert(0, str(PROJECT_ROOT))

# Force CPU execution to prevent CUDA OOM
os.environ["CUDA_VISIBLE_DEVICES"] = ""

def main():
    port = 33999
    print(f"Starting fresh backend server on port {port}...")
    
    # Start Uvicorn process
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    
    try:
        # Wait for server to become healthy
        healthy = False
        for _ in range(30):
            try:
                r = requests.get(f"http://127.0.0.1:{port}/health", timeout=1)
                if r.ok:
                    healthy = True
                    break
            except Exception:
                pass
            time.sleep(0.5)
            
        if not healthy:
            print("Failed to start server.")
            sys.exit(1)
            
        print("Backend server is healthy. Running test suite...")
        
        # Run test runner script
        cmd = [sys.executable, "run_tests.py", "--port", str(port)]
        res = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
        
        sys.exit(res.returncode)
        
    finally:
        print("Terminating backend server...")
        proc.terminate()
        proc.wait()

if __name__ == "__main__":
    main()
