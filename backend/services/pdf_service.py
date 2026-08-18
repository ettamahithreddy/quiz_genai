import os
import re
import pymupdf
from typing import Dict, List, Any

def clean_extracted_text(text: str) -> str:
    """Normalize whitespace, remove excessive newlines and unwanted control characters."""
    if not text:
        return ""
    # Replace non-breaking spaces
    text = text.replace("\xa0", " ")
    # Replace multiple newlines with double newline (paragraph break)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    # Replace horizontal whitespace with single space
    text = re.sub(r"[ \t]+", " ", text)
    # Strip leading and trailing whitespace
    return text.strip()

def extract_text_from_pdf(file_path: str) -> Dict[str, Any]:
    """
    Extracts text page-by-page from a PDF file using PyMuPDF.
    Returns dictionary with page-level texts and metadata.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found at path: {file_path}")

    doc = pymupdf.open(file_path)
    total_pages = len(doc)
    pages_data = []
    full_text_list = []

    for page_index in range(total_pages):
        page = doc[page_index]
        raw_text = page.get_text("text")
        cleaned_text = clean_extracted_text(raw_text)
        
        # Store even if empty so page numbers are strictly 1-indexed
        pages_data.append({
            "page_number": page_index + 1,
            "text": cleaned_text,
            "char_count": len(cleaned_text),
            "word_count": len(cleaned_text.split()) if cleaned_text else 0
        })
        if cleaned_text:
            full_text_list.append(f"--- Page {page_index + 1} ---\n{cleaned_text}")

    doc.close()

    total_characters = sum(p["char_count"] for p in pages_data)
    total_words = sum(p["word_count"] for p in pages_data)

    return {
        "total_pages": total_pages,
        "total_characters": total_characters,
        "total_words": total_words,
        "pages": pages_data,
        "full_text": "\n\n".join(full_text_list)
    }

def extract_text_from_plain_text(text_content: str, title: str = "Pasted Study Material") -> Dict[str, Any]:
    """
    Process pasted text/article or plain text notes.
    Virtualizes it into page segments (approx 1500 chars/page) for consistent pagination.
    """
    cleaned_text = clean_extracted_text(text_content)
    total_chars = len(cleaned_text)
    
    # Segment into virtual pages of ~1500 chars
    page_size = 1500
    pages_data = []
    
    if not cleaned_text:
        pages_data.append({
            "page_number": 1,
            "text": "",
            "char_count": 0,
            "word_count": 0
        })
    else:
        chunks = [cleaned_text[i:i+page_size] for i in range(0, len(cleaned_text), page_size)]
        for idx, chunk in enumerate(chunks):
            pages_data.append({
                "page_number": idx + 1,
                "text": chunk,
                "char_count": len(chunk),
                "word_count": len(chunk.split())
            })

    return {
        "total_pages": len(pages_data),
        "total_characters": total_chars,
        "total_words": len(cleaned_text.split()) if cleaned_text else 0,
        "pages": pages_data,
        "full_text": cleaned_text
    }
