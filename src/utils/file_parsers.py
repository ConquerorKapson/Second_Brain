"""
File parsers for PDFs, DOCX, images (OCR), HTML scraping.
Keep parsers small and testable.
"""
"""
File parsers for PDFs, text, HTML.
Keep parsers small and testable.
"""
import io
from typing import List
import pdfplumber

def parse_pdf_bytes(file_bytes: bytes) -> List[str]:
    """
    Return list of page texts extracted from PDF bytes.
    Each element corresponds to one page's text (strings).
    """
    texts: List[str] = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            texts.append(t or "")
    return texts

def parse_text_bytes(file_bytes: bytes, encoding: str = "utf-8") -> List[str]:
    """
    Return one-element list containing the text content decoded from bytes.
    """
    try:
        text = file_bytes.decode(encoding)
    except Exception:
        # fallback: replace errors
        text = file_bytes.decode(encoding, errors="replace")
    return [text]

def detect_file_type_from_bytes(file_bytes: bytes, filename: str = "") -> str:
    """
    Very light-weight file type hint:
    - returns 'pdf' if bytes look like PDF
    - else returns 'text'
    """
    if file_bytes[:4] == b"%PDF":
        return "pdf"
    # quick heuristic: if filename endswith .pdf
    if filename.lower().endswith(".pdf"):
        return "pdf"
    return "text"
