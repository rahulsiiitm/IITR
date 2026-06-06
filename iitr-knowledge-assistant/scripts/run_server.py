#!/usr/bin/env python3
"""Start FastAPI on an OS-assigned port (port 0) so Cursor cannot pre-bind it."""

from __future__ import annotations

import os
os.environ["CUDA_VISIBLE_DEVICES"] = ""
import re
import subprocess
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent


def write_api_config(port: int) -> None:
    sys.path.insert(0, str(ROOT))
    from backend.config import settings
    path = ROOT / "frontend" / "api-config.js"
    api_key_line = f"\nwindow.API_KEY = '{settings.api_key}';" if settings.api_key else ""
    path.write_text(
        f"window.API_SAME_ORIGIN = true;\nwindow.API_PORT = {port};{api_key_line}\n",
        encoding="utf-8",
    )


def find_running_server() -> int | None:
    try:
        out = subprocess.check_output(["ss", "-tlnp"], text=True, stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None

    for line in out.splitlines():
        if "uvicorn" not in line and "python" not in line:
            continue
        match = re.search(r"127\.0\.0\.1:(\d+)", line)
        if not match:
            continue
        port = int(match.group(1))
        try:
            r = requests.get(f"http://127.0.0.1:{port}/health", timeout=0.5)
            if r.ok and "index_loaded" in r.json():
                return port
        except requests.RequestException:
            pass
    return None


def port_for_pid(pid: int) -> int | None:
    try:
        out = subprocess.check_output(["ss", "-tlnp"], text=True, stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None

    for line in out.splitlines():
        if f"pid={pid}," not in line and f"pid={pid})" not in line:
            continue
        match = re.search(r"127\.0\.0\.1:(\d+)", line)
        if match:
            return int(match.group(1))
    return None





def main() -> None:
    os.chdir(ROOT)
    existing = find_running_server()
    if existing:
        write_api_config(existing)
        print("API already running.")
        print()
        print(f"  Open chat:  http://127.0.0.1:{existing}/")
        print(f"  Health:     http://127.0.0.1:{existing}/health")
        return

    venv_python = ROOT / "venv" / "bin" / "python"
    python = str(venv_python if venv_python.exists() else sys.executable)

    # Port 0 = OS picks a free port; Cursor cannot steal it from the command line
    proc = subprocess.Popen(
        [
            python,
            "-m",
            "uvicorn",
            "backend.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "45123",
        ],
        cwd=ROOT,
    )

    port = None
    deadline = time.time() + 60
    while time.time() < deadline:
        if proc.poll() is not None:
            print("Server exited before binding. Check errors above.", file=sys.stderr)
            raise SystemExit(1)
        port = port_for_pid(proc.pid)
        if port:
            try:
                r = requests.get(f"http://127.0.0.1:{port}/health", timeout=1)
                if r.ok:
                    break
            except requests.RequestException:
                pass
        time.sleep(0.3)

    if not port:
        proc.terminate()
        raise SystemExit("Server did not become healthy in time.")

    write_api_config(port)
    print()
    print(f"  Open chat:  http://127.0.0.1:{port}/")
    print(f"  Health:     http://127.0.0.1:{port}/health")
    print(f"  Forward port {port} in Cursor Ports (SSH remote), then open that URL")
    print()

    proc.wait()


if __name__ == "__main__":
    main()
