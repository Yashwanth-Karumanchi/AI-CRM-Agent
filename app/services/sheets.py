import gspread
from google.oauth2.service_account import Credentials
from typing import Optional, List
import uuid
import json
import os
import asyncio
import time
from datetime import datetime, date
from app.config import get_settings
from app.logger import get_logger

logger = get_logger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

CLIENT_HEADERS = [
    "Client ID", "Created At", "Name", "Company",
    "Email", "Phone", "Service", "Priority", "Stage",
    "Folder URL", "Report URL", "Next Follow-up",
    "Notes", "Archived"
]

ACTIVITY_HEADERS = [
    "Activity ID", "Client ID", "Timestamp",
    "Type", "Description", "Result", "Resource URL"
]

AUDIT_HEADERS = [
    "Audit ID", "Client ID", "Timestamp", "Field",
    "Old Value", "New Value", "Changed By"
]

LOG_HEADERS = [
    "Log ID", "Timestamp", "Type",
    "Input", "Output", "Error"
]

# ── In-memory cache ────────────────────────────────────
_cache: dict = {}
_CACHE_TTL = 30          # seconds for client records
_ACTIVITY_CACHE_TTL = 15  # seconds for activity records


def _cache_get(key: str):
    entry = _cache.get(key)
    if entry is None:
        return None
    ttl = (
        _ACTIVITY_CACHE_TTL
        if key.startswith("activities_")
        else _CACHE_TTL
    )
    if time.time() - entry["ts"] < ttl:
        return entry["data"]
    # Expired — remove it
    _cache.pop(key, None)
    return None


def _cache_set(key: str, data):
    _cache[key] = {"data": data, "ts": time.time()}


def _cache_clear(key: str = None):
    """Clear one key or entire cache"""
    if key:
        _cache.pop(key, None)
    else:
        _cache.clear()


# ── Deleted clients store ──────────────────────────────
# Holds recently deleted client data for 1-hour undo
_deleted_clients: dict = {}
_DELETED_TTL = 3600  # 1 hour


def store_deleted_client(client_data: dict):
    """Store a deleted client for potential undo"""
    _deleted_clients[client_data["client_id"]] = {
        "data": client_data,
        "deleted_at": time.time()
    }
    logger.info(
        f"Stored deleted client for undo: "
        f"{client_data.get('client_id')}"
    )


def get_deleted_client(client_id: str) -> Optional[dict]:
    """Retrieve a recently deleted client by ID"""
    entry = _deleted_clients.get(client_id)
    if entry and (
        time.time() - entry["deleted_at"] < _DELETED_TTL
    ):
        return entry["data"]
    return None


def get_last_deleted_client() -> Optional[dict]:
    """Get the most recently deleted client"""
    if not _deleted_clients:
        return None
    latest_id, latest_entry = max(
        _deleted_clients.items(),
        key=lambda x: x[1]["deleted_at"]
    )
    if time.time() - latest_entry["deleted_at"] < _DELETED_TTL:
        return latest_entry["data"]
    return None


# ── Spreadsheet connection ─────────────────────────────
_spreadsheet = None
_spreadsheet_ts: float = 0
_CONN_TTL = 300  # reconnect every 5 minutes


def _get_sheets_client():
    """Build authenticated gspread client"""
    creds_env = os.getenv("GOOGLE_CREDENTIALS")
    if creds_env:
        try:
            creds_info = json.loads(creds_env)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"GOOGLE_CREDENTIALS is not valid JSON: {e}"
            )
        creds = Credentials.from_service_account_info(
            creds_info, scopes=SCOPES
        )
    elif os.path.exists("credentials.json"):
        creds = Credentials.from_service_account_file(
            "credentials.json", scopes=SCOPES
        )
    else:
        raise ValueError(
            "No Google credentials found. "
            "Set GOOGLE_CREDENTIALS env var in Render."
        )
    return gspread.authorize(creds)


def _get_spreadsheet_sync():
    """
    Get cached spreadsheet connection.
    Reconnects every _CONN_TTL seconds to handle
    Render sleep and token expiry.
    Sync — must run in thread pool.
    """
    global _spreadsheet, _spreadsheet_ts

    now = time.time()
    if (
        _spreadsheet is None or
        now - _spreadsheet_ts > _CONN_TTL
    ):
        settings = get_settings()
        client = _get_sheets_client()
        _spreadsheet = client.open_by_key(
            settings.spreadsheet_id
        )
        _spreadsheet_ts = now
        logger.info("Google Sheets connection established")

    return _spreadsheet


def get_spreadsheet():
    """Public sync accessor — used by importer"""
    return _get_spreadsheet_sync()


async def _run(fn, *args, **kwargs):
    """
    Run any sync gspread function in thread pool.
    Never blocks the async event loop.
    """
    if kwargs:
        from functools import partial
        fn = partial(fn, **kwargs)
    return await asyncio.to_thread(fn, *args)


# ── Setup ──────────────────────────────────────────────

def setup_sheets():
    """
    Initialise all required worksheets.
    Called once at startup — sync is fine here.
    """
    spreadsheet = _get_spreadsheet_sync()
    existing = [ws.title for ws in spreadsheet.worksheets()]

    config = {
        "Clients": CLIENT_HEADERS,
        "Activities": ACTIVITY_HEADERS,
        "Audit Log": AUDIT_HEADERS,
        "Agent Logs": LOG_HEADERS
    }

    for sheet_name, headers in config.items():
        if sheet_name not in existing:
            ws = spreadsheet.add_worksheet(
                title=sheet_name,
                rows=1000,
                cols=len(headers)
            )
            ws.append_row(headers)
            logger.info(f"Created sheet: {sheet_name}")
        else:
            logger.info(f"Sheet exists: {sheet_name}")


# ── Helpers ────────────────────────────────────────────

def _row_to_client(row: dict, index: int) -> dict:
    """Map a raw gspread record to a clean client dict"""
    return {
        "row_number": index + 2,
        "client_id": str(row.get("Client ID", "")),
        "created_at": str(row.get("Created At", "")),
        "name": str(row.get("Name", "")),
        "company": str(row.get("Company", "")),
        "email": str(row.get("Email", "")),
        "phone": str(row.get("Phone", "")),
        "service": str(row.get("Service", "")),
        "priority": str(row.get("Priority", "Medium")),
        "stage": str(row.get("Stage", "New")),
        "folder_url": str(row.get("Folder URL", "")),
        "report_url": str(row.get("Report URL", "")),
        "next_follow_up": str(
            row.get("Next Follow-up", "")
        ),
        "notes": str(row.get("Notes", "")),
        "archived": str(row.get("Archived", "No"))
    }


def _get_all_records_sync() -> List[dict]:
    """
    Fetch all client records with caching.
    Sync — runs in thread pool.
    """
    cached = _cache_get("all_records")
    if cached is not None:
        return cached

    spreadsheet = _get_spreadsheet_sync()
    ws = spreadsheet.worksheet("Clients")
    records = ws.get_all_records()

    _cache_set("all_records", records)
    return records


async def _get_all_records() -> List[dict]:
    """Async wrapper — never blocks event loop"""
    return await _run(_get_all_records_sync)


# ── Sync helpers for thread pool callers ───────────────

def get_all_clients_sync(
    limit: int = 10000,
    include_archived: bool = False
) -> List[dict]:
    """
    Sync version for importer duplicate checking.
    Must be called from thread pool.
    """
    records = _get_all_records_sync()
    clients = []
    for i, r in enumerate(records):
        if not r.get("Client ID"):
            continue
        if (
            not include_archived and
            str(r.get("Archived", "No")).lower() in
            ("yes", "true")
        ):
            continue
        clients.append(_row_to_client(r, i))
    return clients[:limit]


# ── Create ─────────────────────────────────────────────

def _create_client_sync(data: dict) -> dict:
    """
    Create a single client.
    Sync — runs in thread pool.
    Validates email uniqueness before inserting.
    """
    spreadsheet = _get_spreadsheet_sync()
    ws = spreadsheet.worksheet("Clients")

    # Duplicate email check
    if data.get("email"):
        records = ws.get_all_records()
        duplicate = next(
            (
                r for r in records
                if r.get("Email", "").strip().lower() ==
                str(data["email"]).strip().lower()
                and str(r.get("Archived", "No")).lower()
                not in ("yes", "true")
            ),
            None
        )
        if duplicate:
            raise ValueError(
                f"A client with email '{data['email']}' "
                f"already exists: "
                f"{duplicate.get('Client ID')}"
            )

    client_id = "CL-" + str(uuid.uuid4())[:8].upper()
    now = datetime.utcnow().isoformat()

    row = [
        client_id,
        now,
        str(data.get("name", "")),
        str(data.get("company", "") or ""),
        str(data.get("email", "") or ""),
        str(data.get("phone", "") or ""),
        str(data.get("service", "") or ""),
        str(data.get("priority", "Medium")),
        str(data.get("stage", "New")),
        "",   # Folder URL
        "",   # Report URL
        "",   # Next Follow-up
        str(data.get("notes", "") or ""),
        "No"  # Archived
    ]

    ws.append_row(row, value_input_option="RAW")
    _cache_clear("all_records")

    return {
        "client_id": client_id,
        "created_at": now,
        "name": data.get("name"),
        "company": data.get("company"),
        "email": data.get("email"),
        "phone": data.get("phone"),
        "service": data.get("service"),
        "priority": data.get("priority", "Medium"),
        "stage": data.get("stage", "New"),
        "notes": data.get("notes"),
        "archived": "No"
    }


async def create_client(data: dict) -> dict:
    """Create a client — non-blocking"""
    client = await _run(_create_client_sync, data)

    # Fire-and-forget logging
    asyncio.create_task(log_activity(
        client["client_id"],
        "CLIENT_CREATED",
        f"Created client: {client['name']}",
        "SUCCESS",
        ""
    ))

    logger.info(f"Client created: {client['client_id']}")
    return client


# ── Batch Create ───────────────────────────────────────

def _batch_create_sync(rows: List[dict]) -> dict:
    """
    Insert all rows in ONE Google Sheets API call.
    Massively faster than one-by-one inserts.
    Sync — runs in thread pool.
    """
    spreadsheet = _get_spreadsheet_sync()
    ws = spreadsheet.worksheet("Clients")
    headers = ws.row_values(1)
    col_index = {h: i for i, h in enumerate(headers)}
    now = datetime.utcnow().isoformat()

    created = []
    failed = []
    batch_rows = []

    for row in rows:
        try:
            client_id = "CL-" + str(uuid.uuid4())[:8].upper()
            sheet_row = [""] * len(headers)

            def set_col(
                field: str,
                value,
                _row=sheet_row,
                _col=col_index
            ):
                if field in _col and value is not None:
                    _row[_col[field]] = str(value)

            set_col("Client ID", client_id)
            set_col("Created At", now)
            set_col("Name", row.get("name", ""))
            set_col("Company", row.get("company", ""))
            set_col("Email", row.get("email", ""))
            set_col("Phone", row.get("phone", ""))
            set_col("Service", row.get("service", ""))
            set_col(
                "Priority",
                row.get("priority", "Medium")
            )
            set_col("Stage", row.get("stage", "New"))
            set_col("Notes", row.get("notes", ""))
            set_col("Archived", "No")
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

    _cache_clear("all_records")
    return {"created": created, "failed": failed}


async def batch_create_clients(rows: List[dict]) -> dict:
    """Batch insert all clients — non-blocking"""
    return await _run(_batch_create_sync, rows)


# ── Read ───────────────────────────────────────────────

async def get_all_clients(
    query: Optional[str] = None,
    stage: Optional[str] = None,
    priority: Optional[str] = None,
    client_id: Optional[str] = None,
    email: Optional[str] = None,
    include_archived: bool = False,
    limit: int = 20
) -> List[dict]:
    """Get clients with optional filtering"""
    records = await _get_all_records()
    results = []

    for i, r in enumerate(records):
        # Skip rows without a client ID
        if not r.get("Client ID"):
            continue

        # Archived filter
        is_archived = str(
            r.get("Archived", "No")
        ).lower() in ("yes", "true")
        if not include_archived and is_archived:
            continue

        # Field filters
        if client_id and (
            r.get("Client ID", "").lower() !=
            client_id.lower()
        ):
            continue
        if email and (
            r.get("Email", "").lower() !=
            email.lower()
        ):
            continue
        if stage and (
            r.get("Stage", "").lower() !=
            stage.lower()
        ):
            continue
        if priority and (
            r.get("Priority", "").lower() !=
            priority.lower()
        ):
            continue

        # Text search across all fields
        if query:
            searchable = " ".join(
                str(v) for v in r.values()
            ).lower()
            if query.lower() not in searchable:
                continue

        results.append(_row_to_client(r, i))

    # Return newest first
    return list(reversed(results))[:limit]


async def get_client_by_id(
    client_id: str
) -> Optional[dict]:
    """Get a single client by ID"""
    records = await _get_all_records()
    for i, r in enumerate(records):
        if (
            r.get("Client ID", "").lower() ==
            client_id.lower()
        ):
            return _row_to_client(r, i)
    return None


async def require_client(client_id: str) -> dict:
    """Get client or raise ValueError if not found"""
    client = await get_client_by_id(client_id)
    if not client:
        raise ValueError(
            f"Client not found: {client_id}"
        )
    return client


# ── Update ─────────────────────────────────────────────

def _update_cell_sync(
    row_number: int,
    col: int,
    value: str
):
    """Update a single cell — sync, runs in thread pool"""
    spreadsheet = _get_spreadsheet_sync()
    ws = spreadsheet.worksheet("Clients")
    ws.update_cell(row_number, col, str(value))
    _cache_clear("all_records")


async def update_client_field(
    row_number: int,
    col: int,
    value: str
):
    """Update a cell — non-blocking"""
    await _run(_update_cell_sync, row_number, col, value)


# Column index map for client fields
_FIELD_COL_MAP = {
    "name": 3,
    "company": 4,
    "email": 5,
    "phone": 6,
    "service": 7,
    "priority": 8,
    "stage": 9,
    "folder_url": 10,
    "report_url": 11,
    "next_follow_up": 12,
    "notes": 13,
    "archived": 14
}


async def update_client(
    client_id: str,
    updates: dict,
    changed_by: str = "api"
) -> Optional[dict]:
    """Update multiple fields on a client"""
    client = await require_client(client_id)
    row = client["row_number"]

    for field, new_value in updates.items():
        col = _FIELD_COL_MAP.get(field)
        if col is None or new_value is None:
            continue

        old_value = client.get(field, "")
        await update_client_field(row, col, str(new_value))

        asyncio.create_task(log_audit(
            client_id, field,
            str(old_value), str(new_value),
            changed_by
        ))

    asyncio.create_task(log_activity(
        client_id,
        "CLIENT_UPDATED",
        f"Updated fields: {', '.join(updates.keys())}",
        "SUCCESS",
        ""
    ))

    return await get_client_by_id(client_id)


async def update_stage(
    client_id: str,
    stage: str,
    changed_by: str = "api"
) -> dict:
    """Update client pipeline stage"""
    client = await require_client(client_id)
    old_stage = client["stage"]

    await update_client_field(
        client["row_number"], _FIELD_COL_MAP["stage"], stage
    )

    asyncio.create_task(log_audit(
        client_id, "stage",
        old_stage, stage, changed_by
    ))
    asyncio.create_task(log_activity(
        client_id,
        "STAGE_UPDATED",
        f"Stage: {old_stage} → {stage}",
        "SUCCESS",
        ""
    ))

    return {
        "client_id": client_id,
        "previous_stage": old_stage,
        "new_stage": stage
    }


async def update_next_followup(
    client_id: str,
    follow_up_date: str
) -> dict:
    """Set the next follow-up date"""
    client = await require_client(client_id)
    old_date = client.get("next_follow_up", "")

    await update_client_field(
        client["row_number"],
        _FIELD_COL_MAP["next_follow_up"],
        follow_up_date
    )

    asyncio.create_task(log_audit(
        client_id, "next_follow_up",
        old_date, follow_up_date, "api"
    ))
    asyncio.create_task(log_activity(
        client_id,
        "FOLLOWUP_UPDATED",
        f"Follow-up set to {follow_up_date}",
        "SUCCESS",
        ""
    ))

    return {
        "client_id": client_id,
        "previous_follow_up": old_date,
        "next_follow_up": follow_up_date
    }


# ── Archive / Restore / Delete ─────────────────────────

async def archive_client(client_id: str) -> dict:
    """Soft-delete: mark client as archived"""
    client = await require_client(client_id)

    if str(client.get("archived", "No")).lower() in (
        "yes", "true"
    ):
        raise ValueError(
            f"Client {client_id} is already archived"
        )

    await update_client_field(
        client["row_number"],
        _FIELD_COL_MAP["archived"],
        "Yes"
    )

    asyncio.create_task(log_audit(
        client_id, "archived", "No", "Yes", "api"
    ))
    asyncio.create_task(log_activity(
        client_id,
        "CLIENT_ARCHIVED",
        f"Archived: {client['name']}",
        "SUCCESS",
        ""
    ))

    return {"client_id": client_id, "archived": True}


def _restore_client_sync(client_id: str) -> dict:
    """Restore archived client — sync"""
    spreadsheet = _get_spreadsheet_sync()
    ws = spreadsheet.worksheet("Clients")
    records = ws.get_all_records()

    for i, r in enumerate(records):
        if r.get("Client ID") == client_id:
            if str(r.get("Archived", "No")).lower() not in (
                "yes", "true"
            ):
                raise ValueError(
                    f"Client {client_id} is not archived"
                )
            ws.update_cell(i + 2, _FIELD_COL_MAP["archived"] , "No")
            _cache_clear("all_records")
            return {
                "client_id": client_id,
                "name": r.get("Name"),
                "restored": True
            }

    raise ValueError(f"Client not found: {client_id}")


async def restore_client(client_id: str) -> dict:
    """Restore an archived client — non-blocking"""
    result = await _run(_restore_client_sync, client_id)

    asyncio.create_task(log_audit(
        client_id, "archived", "Yes", "No", "api"
    ))
    asyncio.create_task(log_activity(
        client_id,
        "CLIENT_RESTORED",
        f"Restored: {result.get('name')}",
        "SUCCESS",
        ""
    ))

    return result


def _delete_client_sync(client_id: str) -> dict:
    """
    Permanently delete a client row from Sheets.
    Stores client data first for 1-hour undo window.
    Sync — runs in thread pool.
    """
    spreadsheet = _get_spreadsheet_sync()
    ws = spreadsheet.worksheet("Clients")
    records = ws.get_all_records()

    for i, r in enumerate(records):
        if r.get("Client ID") == client_id:
            # Store before deleting
            client_data = _row_to_client(r, i)
            store_deleted_client(client_data)

            ws.delete_rows(i + 2)
            _cache_clear("all_records")

            logger.info(
                f"Permanently deleted client: {client_id}"
            )
            return {
                "client_id": client_id,
                "deleted": True,
                "name": r.get("Name")
            }

    raise ValueError(f"Client not found: {client_id}")


async def delete_client_permanently(
    client_id: str
) -> dict:
    """Permanently delete a client — non-blocking"""
    result = await _run(_delete_client_sync, client_id)

    asyncio.create_task(log_activity(
        client_id,
        "CLIENT_DELETED",
        f"Permanently deleted: {result.get('name')}",
        "SUCCESS",
        ""
    ))

    return result


def _restore_deleted_client_sync(
    client_data: dict
) -> dict:
    """
    Re-insert a permanently deleted client.
    Uses original client_id and all original data.
    Sync — runs in thread pool.
    """
    spreadsheet = _get_spreadsheet_sync()
    ws = spreadsheet.worksheet("Clients")

    # Ensure not already re-inserted
    records = ws.get_all_records()
    existing = next(
        (r for r in records
         if r.get("Client ID") ==
         client_data.get("client_id")),
        None
    )
    if existing:
        raise ValueError(
            f"Client {client_data['client_id']} "
            f"already exists in the sheet"
        )

    row = [
        client_data.get("client_id", ""),
        client_data.get("created_at", ""),
        client_data.get("name", ""),
        client_data.get("company", ""),
        client_data.get("email", ""),
        client_data.get("phone", ""),
        client_data.get("service", ""),
        client_data.get("priority", "Medium"),
        client_data.get("stage", "New"),
        client_data.get("folder_url", ""),
        client_data.get("report_url", ""),
        client_data.get("next_follow_up", ""),
        client_data.get("notes", ""),
        "No"
    ]

    ws.append_row(row, value_input_option="RAW")
    _cache_clear("all_records")

    # Remove from deleted store
    _deleted_clients.pop(
        client_data.get("client_id"), None
    )

    return {
        "client_id": client_data["client_id"],
        "name": client_data.get("name"),
        "restored": True
    }


async def restore_deleted_client(
    client_id: str = None
) -> dict:
    """
    Restore a permanently deleted client.
    Pass client_id to restore specific client,
    or omit to restore the most recently deleted.
    Undo window: 1 hour from deletion.
    """
    if client_id:
        data = get_deleted_client(client_id)
        if not data:
            raise ValueError(
                f"No deleted record found for {client_id}. "
                f"Either not deleted recently or "
                f"1-hour undo window has expired."
            )
    else:
        data = get_last_deleted_client()
        if not data:
            raise ValueError(
                "No recently deleted clients found. "
                "Deletions can only be undone within 1 hour."
            )

    result = await _run(
        _restore_deleted_client_sync, data
    )

    asyncio.create_task(log_activity(
        result["client_id"],
        "CLIENT_RESTORED",
        f"Undo delete: restored {result['name']}",
        "SUCCESS",
        ""
    ))

    return result


async def get_archived_clients() -> List[dict]:
    """Get all archived clients"""
    records = await _get_all_records()
    return [
        _row_to_client(r, i)
        for i, r in enumerate(records)
        if str(r.get("Archived", "No")).lower() in
        ("yes", "true")
    ]


# ── Bulk Operations ────────────────────────────────────

async def bulk_update_stage(
    client_ids: List[str],
    stage: str
) -> dict:
    """Update stage for multiple clients"""
    results = []
    errors = []

    for cid in client_ids:
        try:
            result = await update_stage(cid, stage)
            results.append(result)
        except Exception as e:
            errors.append({
                "client_id": cid,
                "error": str(e)
            })

    return {
        "updated": len(results),
        "failed": len(errors),
        "results": results,
        "errors": errors
    }


async def bulk_archive(client_ids: List[str]) -> dict:
    """Archive multiple clients"""
    results = []
    errors = []

    for cid in client_ids:
        try:
            result = await archive_client(cid)
            results.append(result)
        except Exception as e:
            errors.append({
                "client_id": cid,
                "error": str(e)
            })

    return {
        "archived": len(results),
        "failed": len(errors),
        "results": results,
        "errors": errors
    }


# ── Audit & Rollback ───────────────────────────────────

def _get_audit_records_sync(
    client_id: str
) -> List[dict]:
    """Fetch audit history for a client — sync"""
    cache_key = f"audit_{client_id}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    spreadsheet = _get_spreadsheet_sync()
    ws = spreadsheet.worksheet("Audit Log")
    records = ws.get_all_records()

    result = [
        {
            "audit_id": r.get("Audit ID"),
            "timestamp": r.get("Timestamp"),
            "field": r.get("Field"),
            "old_value": r.get("Old Value"),
            "new_value": r.get("New Value"),
            "changed_by": r.get("Changed By")
        }
        for r in records
        if r.get("Client ID") == client_id
    ]

    _cache_set(cache_key, result)
    return result


async def get_client_audit_history(
    client_id: str
) -> List[dict]:
    """Get audit trail for a client — non-blocking"""
    return await _run(
        _get_audit_records_sync, client_id
    )


async def rollback_client_field(
    client_id: str,
    field: str
) -> dict:
    """Rollback a specific field to its previous value"""
    history = await get_client_audit_history(client_id)
    field_history = [
        h for h in history
        if h.get("field") == field
    ]

    if not field_history:
        raise ValueError(
            f"No history found for field '{field}' "
            f"on client {client_id}"
        )

    col = _FIELD_COL_MAP.get(field)
    if col is None:
        raise ValueError(
            f"Field '{field}' cannot be rolled back. "
            f"Supported: {list(_FIELD_COL_MAP.keys())}"
        )

    last_change = field_history[-1]
    old_value = str(last_change.get("old_value", ""))

    client = await require_client(client_id)
    current_value = str(client.get(field, ""))

    await update_client_field(
        client["row_number"], col, old_value
    )

    # Clear audit cache for this client
    _cache_clear(f"audit_{client_id}")

    asyncio.create_task(log_audit(
        client_id, field,
        current_value, old_value, "rollback"
    ))
    asyncio.create_task(log_activity(
        client_id,
        "FIELD_ROLLED_BACK",
        f"Rolled back '{field}': "
        f"'{current_value}' → '{old_value}'",
        "SUCCESS",
        ""
    ))

    return {
        "client_id": client_id,
        "field": field,
        "rolled_back_from": current_value,
        "rolled_back_to": old_value
    }


async def rollback_last_change(client_id: str) -> dict:
    """Rollback the most recent change to a client"""
    history = await get_client_audit_history(client_id)

    if not history:
        raise ValueError(
            f"No change history found for {client_id}"
        )

    # Skip rollback entries themselves
    real_changes = [
        h for h in history
        if h.get("changed_by") != "rollback"
    ]

    if not real_changes:
        raise ValueError(
            f"No reversible changes found for {client_id}"
        )

    last_change = real_changes[-1]
    return await rollback_client_field(
        client_id, last_change["field"]
    )


# ── Follow-ups ─────────────────────────────────────────

async def get_followups_due() -> List[dict]:
    """Get clients with overdue follow-ups"""
    today = date.today().isoformat()
    clients = await get_all_clients(limit=None)

    return [
        c for c in clients
        if c.get("next_follow_up") and
        c["next_follow_up"] <= today and
        c.get("stage") not in ("Won", "Lost")
    ]


# ── Pipeline ───────────────────────────────────────────

async def get_pipeline_summary() -> dict:
    """Get aggregated pipeline statistics"""
    clients = await get_all_clients(limit=None)

    stages = [
        "New", "Contacted",
        "Consultation Scheduled",
        "Proposal Sent", "Won", "Lost"
    ]
    stage_counts = {s: 0 for s in stages}

    for c in clients:
        stage = c.get("stage", "New")
        if stage in stage_counts:
            stage_counts[stage] += 1
        else:
            stage_counts[stage] = 1

    high_priority = [
        c for c in clients
        if c.get("priority") == "High" and
        c.get("stage") not in ("Won", "Lost")
    ]
    won = [
        c for c in clients
        if c.get("stage") == "Won"
    ]
    lost = [
        c for c in clients
        if c.get("stage") == "Lost"
    ]

    return {
        "total_clients": len(clients),
        "stage_counts": stage_counts,
        "won_count": len(won),
        "lost_count": len(lost),
        "high_priority_pending_count": len(high_priority),
        "high_priority_pending_clients": [
            {
                "client_id": c["client_id"],
                "name": c["name"],
                "company": c["company"],
                "stage": c["stage"],
                "next_follow_up": c["next_follow_up"]
            }
            for c in high_priority
        ]
    }


# ── Activity Log ───────────────────────────────────────

def _log_activity_sync(
    client_id: str,
    activity_type: str,
    description: str,
    result: str,
    resource_url: str
):
    """Append activity row — sync"""
    spreadsheet = _get_spreadsheet_sync()
    ws = spreadsheet.worksheet("Activities")
    ws.append_row([
        "ACT-" + str(uuid.uuid4())[:8].upper(),
        client_id,
        datetime.utcnow().isoformat(),
        activity_type,
        str(description)[:500],
        result,
        str(resource_url)[:200]
    ])
    # Clear activity cache for this client
    _cache_clear(f"activities_{client_id}")


async def log_activity(
    client_id: str,
    activity_type: str,
    description: str,
    result: str,
    resource_url: str
):
    """Log activity — non-blocking, swallows errors"""
    try:
        await _run(
            _log_activity_sync,
            client_id,
            activity_type,
            description,
            result,
            resource_url
        )
    except Exception as e:
        logger.error(f"Activity log failed: {e}")


async def get_client_activities(
    client_id: str
) -> List[dict]:
    """Get all activities for a client — cached"""

    def _sync():
        cache_key = f"activities_{client_id}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

        spreadsheet = _get_spreadsheet_sync()
        ws = spreadsheet.worksheet("Activities")
        records = ws.get_all_records()

        result = [
            {
                "activity_id": r.get("Activity ID"),
                "timestamp": r.get("Timestamp"),
                "type": r.get("Type"),
                "description": r.get("Description"),
                "result": r.get("Result"),
                "resource_url": r.get("Resource URL")
            }
            for r in records
            if r.get("Client ID") == client_id
        ]

        _cache_set(cache_key, result)
        return result

    return await _run(_sync)


async def search_activities(
    activity_type: Optional[str] = None,
    client_id: Optional[str] = None,
    limit: int = 50
) -> List[dict]:
    """Search activities with optional filters"""

    def _sync():
        spreadsheet = _get_spreadsheet_sync()
        ws = spreadsheet.worksheet("Activities")
        records = ws.get_all_records()

        results = [
            {
                "activity_id": r.get("Activity ID"),
                "client_id": r.get("Client ID"),
                "timestamp": r.get("Timestamp"),
                "type": r.get("Type"),
                "description": r.get("Description"),
                "result": r.get("Result"),
                "resource_url": r.get("Resource URL")
            }
            for r in records
            if (
                not client_id or
                r.get("Client ID") == client_id
            ) and (
                not activity_type or
                r.get("Type") == activity_type
            )
        ]

        return list(reversed(results))[:limit]

    return await _run(_sync)


# ── Audit Log ──────────────────────────────────────────

def _log_audit_sync(
    client_id: str,
    field: str,
    old_value: str,
    new_value: str,
    changed_by: str
):
    """Append audit row — sync"""
    spreadsheet = _get_spreadsheet_sync()
    ws = spreadsheet.worksheet("Audit Log")
    ws.append_row([
        "AUD-" + str(uuid.uuid4())[:8].upper(),
        client_id,
        datetime.utcnow().isoformat(),
        field,
        str(old_value)[:500],
        str(new_value)[:500],
        changed_by
    ])
    _cache_clear(f"audit_{client_id}")


async def log_audit(
    client_id: str,
    field: str,
    old_value: str,
    new_value: str,
    changed_by: str
):
    """Log audit entry — non-blocking, swallows errors"""
    try:
        await _run(
            _log_audit_sync,
            client_id, field,
            old_value, new_value, changed_by
        )
    except Exception as e:
        logger.error(f"Audit log failed: {e}")


# ── Agent Logs ─────────────────────────────────────────

def _log_agent_sync(
    log_type: str,
    input_text: str,
    output_text: str,
    error: str
):
    """Append agent log row — sync"""
    spreadsheet = _get_spreadsheet_sync()
    ws = spreadsheet.worksheet("Agent Logs")
    ws.append_row([
        "LOG-" + str(uuid.uuid4())[:8].upper(),
        datetime.utcnow().isoformat(),
        log_type,
        str(input_text)[:500],
        str(output_text)[:500],
        str(error)[:200]
    ])


async def log_agent(
    log_type: str,
    input_text: str,
    output_text: str,
    error: str = ""
):
    """Log agent operation — non-blocking, swallows errors"""
    try:
        await _run(
            _log_agent_sync,
            log_type, input_text, output_text, error
        )
    except Exception as e:
        logger.error(f"Agent log failed: {e}")