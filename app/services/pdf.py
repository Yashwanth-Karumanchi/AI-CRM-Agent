import pdfplumber
import io
from app.logger import get_logger

logger = get_logger(__name__)

def extract_pdf_text(file_bytes: bytes) -> dict:
    """Extract all text and tables from a PDF file"""
    full_text = []
    all_tables = []
    page_count = 0

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        page_count = len(pdf.pages)

        for page_num, page in enumerate(pdf.pages, 1):
            # Extract text
            text = page.extract_text()
            if text:
                full_text.append(f"--- Page {page_num} ---\n{text}")

            # Extract tables
            tables = page.extract_tables()
            if tables:
                for table in tables:
                    cleaned_table = [
                        [str(cell) if cell else "" for cell in row]
                        for row in table
                    ]
                    all_tables.append({
                        "page": page_num,
                        "data": cleaned_table
                    })

    raw_text = "\n\n".join(full_text)

    logger.info(
        f"Extracted PDF: {page_count} pages, "
        f"{len(raw_text)} chars, "
        f"{len(all_tables)} tables"
    )

    return {
        "raw_text": raw_text,
        "tables": all_tables,
        "page_count": page_count,
        "word_count": len(raw_text.split()),
        "has_tables": len(all_tables) > 0
    }