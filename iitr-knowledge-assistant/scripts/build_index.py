#!/usr/bin/env python3
"""CLI to ingest PDF and build persistent FAISS index."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import settings
from backend.indexing.build_index import build_and_save_index


def main() -> None:
    print(f"USING FAISS PATH: {settings.faiss_index_path}")
    print(f"Reading PDFs from: {settings.data_dir}")
    
    print("Building FAISS index (this may take a moment)...")
    _, chunks = build_and_save_index()
    print(f"  Index saved to: {settings.faiss_index_path}")
    print(f"  Metadata saved to: {settings.chunks_metadata_path}")
    print(f"  Total chunks indexed: {len(chunks)}")


if __name__ == "__main__":
    main()
