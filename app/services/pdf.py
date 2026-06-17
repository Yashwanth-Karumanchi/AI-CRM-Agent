import pdfplumber
import io
from app.logger import get_logger

logger = get_logger(__name__)

# Max chars to extract — prevents huge prompts
MAX_TEXT_CHARS = 8000
MAX_PAGES = 20


def extract_pdf_text(file_bytes: bytes) -> dict:
    """
    Extract text and tables from a PDF file.
    Caps at MAX_PAGES and MAX_TEXT_CHARS for LLM safety.
    Returns structured dict ready for AI processing.
    """
    if not file_bytes:
        raise ValueError("PDF file is empty")

    full_text: list[str] = []
    all_tables: list[dict] = []
    page_count = 0

    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            page_count = len(pdf.pages)
            pages_to_process = min(page_count, MAX_PAGES)

            for page_num, page in enumerate(
                pdf.pages[:pages_to_process], 1
            ):
                try:
                    # Extract text
                    text = page.extract_text()
                    if text and text.strip():
                        full_text.append(
                            f"--- Page {page_num} ---\n"
                            f"{text.strip()}"
                        )
                except Exception as e:
                    logger.warning(
                        f"Page {page_num} text failed: {e}"
                    )

                try:
                    # Extract tables
                    tables = page.extract_tables()
                    if tables:
                        for table in tables:
                            if not table:
                                continue
                            cleaned = [
                                [
                                    str(cell).strip()
                                    if cell is not None
                                    else ""
                                    for cell in row
                                ]
                                for row in table
                                if row
                            ]
                            if cleaned:
                                all_tables.append({
                                    "page": page_num,
                                    "data": cleaned
                                })
                except Exception as e:
                    logger.warning(
                        f"Page {page_num} table failed: {e}"
                    )

    except Exception as e:
        raise ValueError(
            f"Could not read PDF file: {e}. "
            f"Ensure the file is a valid PDF."
        )

    raw_text = "\n\n".join(full_text)

    # Cap text length for LLM
    truncated = len(raw_text) > MAX_TEXT_CHARS
    if truncated:
        raw_text = raw_text[:MAX_TEXT_CHARS]
        logger.info(
            f"PDF text truncated to {MAX_TEXT_CHARS} chars"
        )

    if not raw_text.strip():
        raise ValueError(
            "Could not extract any text from this PDF. "
            "The file may be scanned or image-based."
        )

    logger.info(
        f"PDF extracted: {page_count} pages "
        f"({pages_to_process} processed), "
        f"{len(raw_text)} chars, "
        f"{len(all_tables)} tables, "
        f"truncated={truncated}"
    )

    return {
        "raw_text": raw_text,
        "tables": all_tables,
        "page_count": page_count,
        "pages_processed": pages_to_process,
        "word_count": len(raw_text.split()),
        "char_count": len(raw_text),
        "has_tables": len(all_tables) > 0,
        "truncated": truncated
    }