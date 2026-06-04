from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.config import settings


def chunk_pages(
    pages: list[dict],
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[dict]:
    """Split page texts into smaller chunks.

    Returns:
        List of dicts: [{"text": "...", "page": 1, "full_page": "..."}, ...]
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size or settings.chunk_size,
        chunk_overlap=chunk_overlap or settings.chunk_overlap,
        separators=["\n\n", "\n", ". ", " "],
    )

    chunks: list[dict] = []

    for page_data in pages:
        page_num = page_data["page"]
        text = page_data["text"]
        split_texts = splitter.split_text(text)

        for chunk_text in split_texts:
            chunks.append(
                {
                    "text": chunk_text,
                    "page": page_num,
                    "full_page": text,
                }
            )

    return chunks
