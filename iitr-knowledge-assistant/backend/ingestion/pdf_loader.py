import fitz


def extract_pages(pdf_path: str) -> list[dict]:
    """Extract text from each page of a PDF.

    Returns:
        List of dicts: [{"page": 1, "text": "..."}, ...]
    """
    doc = fitz.open(pdf_path)
    pages = []

    for i, page in enumerate(doc):
        text = page.get_text().strip()
        if text:
            pages.append({"page": i + 1, "text": text})

    doc.close()
    return pages
