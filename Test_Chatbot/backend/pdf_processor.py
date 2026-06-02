import fitz  # PyMuPDF


def extract_pages(pdf_path):
    """Extract text from each page of the PDF.
    
    Returns:
        List of dicts: [{"page": 1, "text": "..."}, ...]
    """
    doc = fitz.open(pdf_path)
    pages = []

    for i, page in enumerate(doc):
        text = page.get_text().strip()
        if text:
            pages.append({
                "page": i + 1,
                "text": text
            })

    doc.close()
    return pages


from langchain_text_splitters import RecursiveCharacterTextSplitter

def chunk_pages(pages):
    """Split page texts into smaller chunks using Langchain's RecursiveCharacterTextSplitter.
    
    Returns:
        List of dicts: [{"chunk": "...", "page": 1}, ...]
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=[
            "\n\n",
            "\n",
            ". ",
            " "
        ]
    )

    chunks = []

    for page_data in pages:
        page_num = page_data["page"]
        text = page_data["text"]

        split_texts = splitter.split_text(text)

        for chunk in split_texts:
            chunks.append({
                "chunk": chunk,
                "page": page_num,
                "full_page": text
            })

    return chunks
