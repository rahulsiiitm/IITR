def build_context(context_chunks: list[dict]) -> str:
    """Build page-labeled context string for the LLM prompt.

    Sends individual chunks (not full pages) to avoid wasting the LLM's
    context window.  Chunks from the same page are grouped under a single
    page header for clarity.
    """
    # Group chunks by page number, preserving retrieval order
    pages: dict[int, list[str]] = {}
    for chunk in context_chunks:
        page_num = chunk["page"]
        text = chunk.get("text", chunk.get("chunk", ""))
        if not text:
            continue
        pages.setdefault(page_num, []).append(text)

    parts: list[str] = []
    for page_num, texts in pages.items():
        combined = "\n\n".join(texts)
        parts.append(f"PAGE {page_num}\n\n{combined}")

    return "\n\n".join(parts)
