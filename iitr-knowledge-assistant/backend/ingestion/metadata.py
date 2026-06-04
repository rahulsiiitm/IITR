from backend.config import DocumentConfig, get_document_config


def attach_metadata(
    raw_chunks: list[dict],
    document_key: str = "phd_regulations_2026",
    start_id: int = 1,
) -> list[dict]:
    """Attach document metadata to each chunk.

    Returns chunks with schema:
        chunk_id, document, page, category, year, text, full_page, index
    """
    doc_config: DocumentConfig = get_document_config(document_key)
    enriched: list[dict] = []

    for idx, chunk in enumerate(raw_chunks):
        enriched.append(
            {
                "chunk_id": start_id + idx,
                "document": doc_config.title,
                "page": chunk["page"],
                "category": doc_config.category,
                "year": doc_config.year,
                "text": chunk["text"],
                "full_page": chunk.get("full_page", chunk["text"]),
                "index": idx,
            }
        )

    return enriched
