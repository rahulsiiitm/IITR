def build_context(context_chunks: list[dict]) -> str:
    """Build page-labeled context string for the LLM prompt."""
    context = ""
    seen_pages: set[int] = set()

    for chunk in context_chunks:
        page_num = chunk["page"]
        if page_num not in seen_pages:
            page_text = chunk.get("full_page", chunk.get("text", chunk.get("chunk", "")))
            context += f"\nPAGE {page_num}\n\n{page_text}\n"
            seen_pages.add(page_num)

    return context.strip()
