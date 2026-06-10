import re
from langchain_text_splitters import RecursiveCharacterTextSplitter
from backend.config import settings

def chunk_pages(
    pages: list[dict],
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[dict]:
    """Split page texts into smaller, cleaned chunks."""
    
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size or settings.chunk_size,
        chunk_overlap=chunk_overlap or settings.chunk_overlap,
        separators=["\n\n", "\n", ".", " ", ""],
        keep_separator=True,
    )

    chunks: list[dict] = []

    for page_data in pages:
        page_num = page_data["page"]
        raw_text = page_data["text"]
        
        # UPGRADE 1: The PDF Text Healer
        # Replaces single line breaks with spaces to fix broken sentences, 
        # but preserves double line breaks (actual paragraphs).
        cleaned_text = re.sub(r'(?<!\n)\n(?!\n)', ' ', raw_text)

        # Pass the healed text to the splitter
        split_texts = splitter.split_text(cleaned_text)

        for chunk_text in split_texts:
            # UPGRADE 2: Strip dangling whitespace or leftover separators
            clean_chunk = chunk_text.strip()
            
            # Skip empty chunks just in case
            if not clean_chunk:
                continue
                
            chunks.append(
                {
                    "text": clean_chunk,
                    "page": page_num,
                    "full_page": cleaned_text,
                }
            )

    return chunks