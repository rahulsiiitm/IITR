#!/usr/bin/env bash
# Launcher — binds port inside Python to avoid Cursor grabbing it between check and uvicorn.
set -e
cd "$(dirname "$0")/.."
source venv/bin/activate
exec python scripts/run_server.py
