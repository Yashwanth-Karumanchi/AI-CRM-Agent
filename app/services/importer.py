import io
import csv
from typing import List, Dict, Tuple
from app.logger import get_logger

logger = get_logger(__name__)

VALID_PRIORITIES = {"High", "Medium", "Low"}
VALID_STAGES = {
    "New", "Contacted",
    "Consultation Scheduled",
    "Proposal Sent", "Won", "Lost"
}

# Flexible column name mapping
COL_MAP = {
    "name":     ["name", "full name", "client name",
                 "contact name", "contact"],
    "email":    ["email", "email address", "e-mail",
                 "mail"],
    "company":  ["company", "organization", "org",
                 "business", "company name"],
    "phone":    ["phone", "phone number", "mobile",
                 "cell", "telephone", "contact number"],
    "service":  ["service", "service type", "product",
                 "interest", "needs"],
    "priority": ["priority", "priority level", "importance"],
    "stage":    ["stage", "pipeline stage", "status"],
    "notes":    ["notes", "note", "comments", "comment",
                 "description", "details"]
}


def _map_columns(headers: List[str]) -> Dict[str, int]:
    """Map spreadsheet headers to our field names"""
    mapping = {}
    headers_lower = [h.strip().lower() for h in headers]

    for field, variants in COL_MAP.items():
        for i, h in enumerate(headers_lower):
            if h in variants:
                mapping[field] = i
                break

    return mapping


def _clean_row(
    row: List[str],
    col_map: Dict[str, int]
) -> Dict:
    """Extract and clean a single row"""
    def get(field):
        idx = col_map.get(field)
        if idx is None or idx >= len(row):
            return None
        val = str(row[idx]).strip()
        return val if val and val.lower() != 'nan' else None

    priority = get("priority")
    if priority and priority.capitalize() in VALID_PRIORITIES:
        priority = priority.capitalize()
    else:
        priority = "Medium"

    stage = get("stage")
    if stage:
        # Try to match stage case-insensitively
        for vs in VALID_STAGES:
            if stage.lower() == vs.lower():
                stage = vs
                break
        else:
            stage = "New"
    else:
        stage = "New"

    return {
        "name": get("name"),
        "email": get("email"),
        "company": get("company"),
        "phone": get("phone"),
        "service": get("service"),
        "priority": priority,
        "stage": stage,
        "notes": get("notes")
    }


def _validate_row(
    row_data: Dict,
    row_num: int
) -> Tuple[bool, str]:
    """Validate a single row. Returns (is_valid, error_msg)"""
    if not row_data.get("name"):
        return False, f"Row {row_num}: Missing name"

    email = row_data.get("email")
    if email and "@" not in email:
        return False, f"Row {row_num}: Invalid email '{email}'"

    return True, ""


def parse_excel(file_bytes: bytes) -> Tuple[
    List[Dict], List[str], List[str]
]:
    """
    Parse Excel file.
    Returns (rows, detected_columns, errors)
    """
    try:
        import openpyxl
    except ImportError:
        raise ValueError(
            "openpyxl not installed. "
            "Run: pip install openpyxl"
        )

    wb = openpyxl.load_workbook(
        io.BytesIO(file_bytes),
        read_only=True,
        data_only=True
    )
    ws = wb.active

    rows = []
    for row in ws.iter_rows(values_only=True):
        rows.append([
            str(cell) if cell is not None else ""
            for cell in row
        ])

    wb.close()

    if not rows:
        raise ValueError("Excel file is empty")

    return _process_rows(rows)


def parse_csv(file_bytes: bytes) -> Tuple[
    List[Dict], List[str], List[str]
]:
    """
    Parse CSV file.
    Returns (rows, detected_columns, errors)
    """
    try:
        text = file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        text = file_bytes.decode("latin-1")

    reader = csv.reader(io.StringIO(text))
    rows = [row for row in reader]

    if not rows:
        raise ValueError("CSV file is empty")

    return _process_rows(rows)


def _process_rows(
    raw_rows: List[List[str]]
) -> Tuple[List[Dict], List[str], List[str]]:
    """
    Process raw rows into client dicts.
    Returns (valid_rows, detected_columns, errors)
    """
    # Find header row (first non-empty row)
    header_row = None
    data_start = 0

    for i, row in enumerate(raw_rows):
        if any(str(cell).strip() for cell in row):
            header_row = row
            data_start = i + 1
            break

    if header_row is None:
        raise ValueError("Could not find header row")

    col_map = _map_columns(header_row)

    if "name" not in col_map:
        raise ValueError(
            "Could not find 'Name' column. "
            "Please ensure your file has a 'Name' header."
        )

    detected_cols = list(col_map.keys())
    valid_rows = []
    errors = []

    seen_emails = set()

    for i, row in enumerate(raw_rows[data_start:], start=data_start + 1):
        # Skip empty rows
        if not any(str(cell).strip() for cell in row):
            continue

        row_data = _clean_row(row, col_map)

        # Validate
        is_valid, err = _validate_row(row_data, i)
        if not is_valid:
            errors.append(err)
            continue

        # Check duplicate email within file
        email = row_data.get("email")
        if email:
            if email.lower() in seen_emails:
                errors.append(
                    f"Row {i}: Duplicate email '{email}' in file"
                )
                continue
            seen_emails.add(email.lower())

        valid_rows.append(row_data)

    return valid_rows, detected_cols, errors


async def bulk_import_clients(
    rows: List[Dict],
    sheets_module,
    check_duplicates: bool = True
) -> Dict:
    """
    Import a list of client dicts into Google Sheets.
    Returns summary dict.
    """
    imported = []
    skipped = []
    failed = []

    # Get existing emails if checking duplicates
    existing_emails = set()
    if check_duplicates:
        try:
            existing = await sheets_module.get_all_clients(
                limit=10000
            )
            existing_emails = {
                c.get("email", "").lower()
                for c in existing
                if c.get("email")
            }
        except Exception as e:
            logger.warning(f"Could not fetch existing emails: {e}")

    for i, row in enumerate(rows):
        try:
            # Check duplicate against existing CRM
            email = row.get("email")
            if (check_duplicates and email and
                    email.lower() in existing_emails):
                skipped.append({
                    "name": row.get("name"),
                    "email": email,
                    "reason": "Email already exists in CRM"
                })
                continue

            client = await sheets_module.create_client(row)
            imported.append({
                "name": client.get("name"),
                "client_id": client.get("client_id"),
                "email": client.get("email")
            })

            # Track new email
            if email:
                existing_emails.add(email.lower())

        except Exception as e:
            failed.append({
                "name": row.get("name", f"Row {i+1}"),
                "error": str(e)
            })

    return {
        "total_rows": len(rows),
        "imported": len(imported),
        "skipped": len(skipped),
        "failed": len(failed),
        "imported_clients": imported,
        "skipped_clients": skipped,
        "failed_clients": failed
    }