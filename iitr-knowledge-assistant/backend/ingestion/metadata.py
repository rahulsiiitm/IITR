
def attach_metadata(
    raw_chunks: list[dict],
    filename: str,
    start_id: int = 1,
) -> list[dict]:
    """Attach document metadata to each chunk.

    Returns chunks with schema:
        chunk_id, document, doc_type, page, text, full_page, index
    """
    # Clean up filename for the title (e.g. "sop_travel_grant.pdf" -> "Sop Travel Grant")
    base_name = filename.replace(".pdf", "")
    title = base_name.replace("_", " ").title()
    
    doc_type = "regulation" if "regulation" in base_name.lower() else "sop"

    enriched: list[dict] = []

    for idx, chunk in enumerate(raw_chunks):
        enriched.append(
            {
                "chunk_id": start_id + idx,
                "document": title,
                "doc_type": doc_type,
                "page": chunk["page"],
                "text": chunk["text"],
                "full_page": chunk.get("full_page", chunk["text"]),
                "index": idx,
            }
        )

    return enriched
