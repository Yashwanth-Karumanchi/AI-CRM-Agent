import io
import csv
import uuid
import asyncio
from datetime import datetime
from typing import List, Dict, Tuple, AsyncGenerator
from app.logger import get_logger

logger = get_logger(__name__)

VALID_PRIORITIES = {"High", "Medium", "Low"}
VALID_STAGES = {
    "New", "Contacted",
    "Consultation Scheduled",
    "Proposal Sent", "Won", "Lost"
}

COL_MAP = {
    "name":     ["name", "full name", "client name",
                 "contact name", "contact"],
    "email":    ["email", "email address", "e-mail", "mail"],
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
    mapping = {}
    headers_lower = [h.strip().lower() for h in headers]
    for field, variants in COL_MAP.items():
        for i, h in enumerate(headers_lower):
            if h in variants:
                mapping[field] = i
                break
    return mapping


def _clean_row(row: List[str], col_map: Dict[str, int]) -> Dict:
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
    row_data: Dict, row_num: int
) -> Tuple[bool, str]:
    if not row_data.get("name"):
        return False, f"Row {row_num}: Missing name"
    email = row_data.get("email")
    if email and "@" not in email:
        return False, f"Row {row_num}: Invalid email '{email}'"
    return True, ""


def _process_rows(
    raw_rows: List[List[str]]
) -> Tuple[List[Dict], List[str], List[str]]:
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
            "Ensure your file has a 'Name' header."
        )

    detected_cols = list(col_map.keys())
    valid_rows = []
    errors = []
    seen_emails = set()

    for i, row in enumerate(raw_rows[data_start:], start=data_start + 1):
        if not any(str(cell).strip() for cell in row):
            continue

        row_data = _clean_row(row, col_map)
        is_valid, err = _validate_row(row_data, i)

        if not is_valid:
            errors.append(err)
            continue

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


def parse_excel(
    file_bytes: bytes
) -> Tuple[List[Dict], List[str], List[str]]:
    try:
        import openpyxl
    except ImportError:
        raise ValueError("openpyxl not installed")

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


def parse_csv(
    file_bytes: bytes
) -> Tuple[List[Dict], List[str], List[str]]:
    try:
        text = file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        text = file_bytes.decode("latin-1")

    reader = csv.reader(io.StringIO(text))
    rows = [row for row in reader]

    if not rows:
        raise ValueError("CSV file is empty")

    return _process_rows(rows)


# ── Sync batch insert (runs in thread pool) ────────────

def _batch_insert_sync(
    rows_to_insert: List[Dict],
    spreadsheet
) -> Tuple[List[Dict], List[Dict]]:
    """
    Single Google Sheets API call to insert all rows.
    This is synchronous — must be called via run_in_thread.
    """
    ws = spreadsheet.worksheet("Clients")
    headers = ws.row_values(1)
    col = {h: i for i, h in enumerate(headers)}
    now = datetime.utcnow().isoformat()

    created = []
    failed = []
    batch_rows = []

    for row in rows_to_insert:
        try:
            client_id = "CL-" + str(uuid.uuid4())[:8].upper()
            sheet_row = [""] * len(headers)

            def set_col(field, value, _row=sheet_row, _col=col):
                if field in _col:
                    _row[_col[field]] = value or ""

            set_col("Client ID", client_id)
            set_col("Created At", now)
            set_col("Name", row.get("name", ""))
            set_col("Company", row.get("company", ""))
            set_col("Email", row.get("email", ""))
            set_col("Phone", row.get("phone", ""))
            set_col("Service", row.get("service", ""))
            set_col("Priority", row.get("priority", "Medium"))
            set_col("Stage", row.get("stage", "New"))
            set_col("Notes", row.get("notes", ""))
            set_col("Archived", "false")
            set_col("Folder URL", "")
            set_col("Report URL", "")
            set_col("Next Follow-up", "")

            batch_rows.append(sheet_row)
            created.append({
                "name": row.get("name"),
                "client_id": client_id,
                "email": row.get("email")
            })
        except Exception as e:
            failed.append({
                "name": row.get("name", "Unknown"),
                "error": str(e)
            })

    if batch_rows:
        ws.append_rows(
            batch_rows,
            value_input_option="RAW",
            insert_data_option="INSERT_ROWS",
            table_range="A1"
        )

    return created, failed


# ── Async streaming import ─────────────────────────────

async def bulk_import_clients_stream(
    rows: List[Dict],
    sheets_module,
    check_duplicates: bool = True
) -> AsyncGenerator[Dict, None]:
    """
    Import clients with live progress events.
    Yields SSE-compatible dicts at each stage.
    """
    total = len(rows)

    yield {
        "type": "start",
        "total": total,
        "message": f"Starting import of {total} clients..."
    }

    await asyncio.sleep(0)

    # Step 1: Check duplicates
    existing_emails = set()
    if check_duplicates:
        yield {
            "type": "progress",
            "step": "checking",
            "message": "Checking for duplicates in CRM...",
            "percent": 10
        }
        await asyncio.sleep(0)

        try:
            from app.services.thread import run_in_thread
            existing = await run_in_thread(
                sheets_module.get_all_clients_sync
            )
            existing_emails = {
                c.get("email", "").lower()
                for c in existing
                if c.get("email")
            }
        except Exception as e:
            logger.warning(f"Could not fetch emails: {e}")

    # Step 2: Filter duplicates
    rows_to_insert = []
    skipped = []
    seen_in_batch = set()

    for row in rows:
        email = (row.get("email") or "").lower()
        if check_duplicates and email:
            if email in existing_emails:
                skipped.append({
                    "name": row.get("name"),
                    "email": row.get("email"),
                    "reason": "Already exists in CRM"
                })
                continue
            if email in seen_in_batch:
                skipped.append({
                    "name": row.get("name"),
                    "email": row.get("email"),
                    "reason": "Duplicate in file"
                })
                continue
            seen_in_batch.add(email)
        rows_to_insert.append(row)

    yield {
        "type": "progress",
        "step": "filtered",
        "message": f"Filtered: {len(rows_to_insert)} to import, "
                   f"{len(skipped)} duplicates skipped",
        "percent": 20,
        "skipped": len(skipped)
    }
    await asyncio.sleep(0)

    if not rows_to_insert:
        yield {
            "type": "complete",
            "imported": 0,
            "skipped": len(skipped),
            "failed": 0,
            "skipped_clients": skipped,
            "imported_clients": [],
            "failed_clients": [],
            "message": "No new clients to import"
        }
        return

    # Step 3: Batch insert in chunks of 25
    # Yields progress after each chunk
    chunk_size = 25
    chunks = [
        rows_to_insert[i:i + chunk_size]
        for i in range(0, len(rows_to_insert), chunk_size)
    ]

    all_created = []
    all_failed = []

    from app.services.thread import run_in_thread
    spreadsheet = await run_in_thread(
        sheets_module.get_spreadsheet
    )

    for i, chunk in enumerate(chunks):
        yield {
            "type": "progress",
            "step": "inserting",
            "message": f"Inserting batch {i+1}/{len(chunks)} "
                       f"({len(chunk)} clients)...",
            "percent": 20 + int(
                (i / len(chunks)) * 70
            ),
            "inserted_so_far": len(all_created)
        }
        await asyncio.sleep(0)

        # Run sync batch insert in thread pool
        created, failed = await run_in_thread(
            _batch_insert_sync, chunk, spreadsheet
        )
        all_created.extend(created)
        all_failed.extend(failed)

        # Emit each created client for live UI update
        for client in created:
            yield {
                "type": "client_added",
                "client": client
            }
            await asyncio.sleep(0)

    # Step 4: Done
    yield {
        "type": "complete",
        "imported": len(all_created),
        "skipped": len(skipped),
        "failed": len(all_failed),
        "imported_clients": all_created,
        "skipped_clients": skipped,
        "failed_clients": all_failed,
        "percent": 100,
        "message": (
            f"Done! {len(all_created)} imported, "
            f"{len(skipped)} skipped, "
            f"{len(all_failed)} failed"
        )
    }


# ── Non-streaming fallback ─────────────────────────────

async def bulk_import_clients(
    rows: List[Dict],
    sheets_module,
    check_duplicates: bool = True
) -> Dict:
    """Non-streaming version for API compatibility"""
    from app.services.thread import run_in_thread

    existing_emails = set()
    if check_duplicates:
        try:
            existing = await run_in_thread(
                sheets_module.get_all_clients_sync
            )
            existing_emails = {
                c.get("email", "").lower()
                for c in existing
                if c.get("email")
            }
        except Exception as e:
            logger.warning(f"Could not fetch emails: {e}")

    rows_to_insert = []
    skipped = []
    seen_in_batch = set()

    for row in rows:
        email = (row.get("email") or "").lower()
        if check_duplicates and email:
            if email in existing_emails or email in seen_in_batch:
                skipped.append({
                    "name": row.get("name"),
                    "email": row.get("email"),
                    "reason": "Duplicate"
                })
                continue
            seen_in_batch.add(email)
        rows_to_insert.append(row)

    if not rows_to_insert:
        return {
            "total_rows": len(rows),
            "imported": 0,
            "skipped": len(skipped),
            "failed": 0,
            "imported_clients": [],
            "skipped_clients": skipped,
            "failed_clients": []
        }

    spreadsheet = await run_in_thread(
        sheets_module.get_spreadsheet
    )
    created, failed = await run_in_thread(
        _batch_insert_sync, rows_to_insert, spreadsheet
    )

    return {
        "total_rows": len(rows),
        "imported": len(created),
        "skipped": len(skipped),
        "failed": len(failed),
        "imported_clients": created,
        "skipped_clients": skipped,
        "failed_clients": failed
    }