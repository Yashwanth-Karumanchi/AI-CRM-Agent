import gspread
from google.oauth2.service_account import Credentials
from typing import Optional, List
import uuid
import json
import os
import asyncio
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

# ── Cached spreadsheet ─────────────────────────────────
_spreadsheet = None


def _get_sheets_client():
    creds_env = os.getenv("GOOGLE_CREDENTIALS")
    if creds_env:
        creds_info = json.loads(creds_env)
        creds = Credentials.from_service_account_info(
            creds_info, scopes=SCOPES
        )
    else:
        creds = Credentials.from_service_account_file(
            "credentials.json", scopes=SCOPES
        )
    return gspread.authorize(creds)


def _get_spreadsheet_sync():
    """Sync — only call from thread pool"""
    global _spreadsheet
    if _spreadsheet is None:
        settings = get_settings()
        client = _get_sheets_client()
        _spreadsheet = client.open_by_key(
            settings.spreadsheet_id
        )
    return _spreadsheet


def get_spreadsheet():
    """Public sync accessor for importer.py"""
    return _get_spreadsheet_sync()


async def _run(fn, *args, **kwargs):
    """
    Run any blocking/sync gspread function
    in a thread pool without blocking the event loop.
    """
    if kwargs:
        from functools import partial
        fn = partial(fn, **kwargs)
    return await asyncio.to_thread(fn, *args)


# ── Setup ──────────────────────────────────────────────

def setup_sheets():
    """Called at startup — sync is fine here"""
    spreadsheet = _get_spreadsheet_sync()
    existing = [s.title for s in spreadsheet.worksheets()]

    sheets_config = {
        "Clients": CLIENT_HEADERS,
        "Activities": ACTIVITY_HEADERS,
        "Audit Log": AUDIT_HEADERS,
        "Agent Logs": LOG_HEADERS
    }

    for sheet_name, headers in sheets_config.items():
        if sheet_name not in existing:
            sheet = spreadsheet.add_worksheet(
                title=sheet_name,
                rows=1000,
                cols=len(headers)
            )
            sheet.append_row(headers)
            logger.info(f"Created sheet: {sheet_name}")
        else:
            logger.info(f"Sheet exists: {sheet_name}")


# ── Helpers ────────────────────────────────────────────

def _row_to_client(row: dict, index: int) -> dict:
    return {
        "row_number": index + 2,
        "client_id": row.get("Client ID", ""),
        "created_at": row.get("Created At", ""),
        "name": row.get("Name", ""),
        "company": row.get("Company", ""),
        "email": row.get("Email", ""),
        "phone": row.get("Phone", ""),
        "service": row.get("Service", ""),
        "priority": row.get("Priority", "Medium"),
        "stage": row.get("Stage", "New"),
        "folder_url": row.get("Folder URL", ""),
        "report_url": row.get("Report URL", ""),
        "next_follow_up": row.get("Next Follow-up", ""),
        "notes": row.get("Notes", ""),
        "archived": row.get("Archived", "No")
    }


def _get_all_records_sync() -> List[dict]:
    """Sync — must run in thread pool"""
    spreadsheet = _get_spreadsheet_sync()
    sheet = spreadsheet.worksheet("Clients")
    return sheet.get_all_records()


async def _get_all_records() -> List[dict]:
    """Async wrapper — never blocks event loop"""
    return await _run(_get_all_records_sync)


# ── Sync versions (for importer thread pool) ───────────

def get_all_clients_sync(
    limit: int = 10000,
    include_archived: bool = False
) -> List[dict]:
    """
    Sync version for use in thread pool via run_in_thread.
    Used by bulk importer for duplicate checking.
    """
    records = _get_all_records_sync()
    clients = []
    for i, r in enumerate(records):
        if not r.get("Client ID"):
            continue
        if not include_archived and r.get("Archived") == "Yes":
            continue
        clients.append(_row_to_client(r, i))
    return clients[:limit]


# ── Create ─────────────────────────────────────────────

def _create_client_sync(data: dict) -> dict:
    """Sync — runs in thread pool"""
    spreadsheet = _get_spreadsheet_sync()
    sheet = spreadsheet.worksheet("Clients")
    records = sheet.get_all_records()

    # Duplicate check
    if data.get("email"):
        duplicate = next(
            (r for r in records
             if r.get("Email", "").lower() ==
             str(data["email"]).lower()
             and r.get("Archived", "") != "Yes"),
            None
        )
        if duplicate:
            raise ValueError(
                f"Client with this email already exists: "
                f"{duplicate['Client ID']}"
            )

    client_id = "CL-" + str(uuid.uuid4())[:8].upper()
    now = datetime.utcnow().isoformat()

    row = [
        client_id, now,
        data.get("name", ""),
        data.get("company", "") or "",
        str(data.get("email", "") or ""),
        data.get("phone", "") or "",
        data.get("service", "") or "",
        data.get("priority", "Medium"),
        data.get("stage", "New"),
        "", "", "",
        data.get("notes", "") or "",
        "No"
    ]

    sheet.append_row(row)

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
    client = await _run(_create_client_sync, data)

    # Log activity without blocking
    asyncio.create_task(log_activity(
        client["client_id"], "CLIENT_CREATED",
        f"Created client: {client['name']}",
        "SUCCESS", ""
    ))

    logger.info(f"Created client: {client['client_id']}")
    return client


# ── Batch Create (for bulk import) ─────────────────────

def _batch_create_sync(rows: List[dict]) -> dict:
    """
    Insert all rows in ONE API call.
    Sync — runs in thread pool.
    """
    spreadsheet = _get_spreadsheet_sync()
    ws = spreadsheet.worksheet("Clients")
    headers = ws.row_values(1)
    col = {h: i for i, h in enumerate(headers)}
    now = datetime.utcnow().isoformat()

    created = []
    failed = []
    batch_rows = []

    for row in rows:
        try:
            client_id = "CL-" + str(uuid.uuid4())[:8].upper()
            sheet_row = [""] * len(headers)

            def set_col(field, value,
                        _row=sheet_row, _col=col):
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

    # Single API call for all rows
    if batch_rows:
        ws.append_rows(
            batch_rows,
            value_input_option="RAW",
            insert_data_option="INSERT_ROWS",
            table_range="A1"
        )

    return {"created": created, "failed": failed}


async def batch_create_clients(rows: List[dict]) -> dict:
    """Async batch insert — never blocks event loop"""
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
    records = await _get_all_records()
    results = []

    for i, r in enumerate(records):
        if not include_archived and r.get("Archived") == "Yes":
            continue
        if client_id and r.get("Client ID", "").lower() != client_id.lower():
            continue
        if email and r.get("Email", "").lower() != email.lower():
            continue
        if stage and r.get("Stage", "").lower() != stage.lower():
            continue
        if priority and r.get("Priority", "").lower() != priority.lower():
            continue
        if query:
            searchable = " ".join(
                str(v) for v in r.values()
            ).lower()
            if query.lower() not in searchable:
                continue
        results.append(_row_to_client(r, i))

    return list(reversed(results))[:limit]


async def get_client_by_id(
    client_id: str
) -> Optional[dict]:
    records = await _get_all_records()
    for i, r in enumerate(records):
        if r.get("Client ID", "").lower() == client_id.lower():
            return _row_to_client(r, i)
    return None


async def require_client(client_id: str) -> dict:
    client = await get_client_by_id(client_id)
    if not client:
        raise ValueError(f"Client not found: {client_id}")
    return client


# ── Update ─────────────────────────────────────────────

def _update_cell_sync(row_number: int, col: int, value: str):
    """Sync cell update — runs in thread pool"""
    spreadsheet = _get_spreadsheet_sync()
    sheet = spreadsheet.worksheet("Clients")
    sheet.update_cell(row_number, col, value)


async def update_client_field(
    row_number: int,
    col: int,
    value: str
):
    await _run(_update_cell_sync, row_number, col, value)


async def update_client(
    client_id: str,
    updates: dict,
    changed_by: str = "api"
) -> dict:
    client = await require_client(client_id)
    row = client["row_number"]

    field_map = {
        "name": 3, "company": 4, "email": 5,
        "phone": 6, "service": 7, "priority": 8,
        "stage": 9, "notes": 13,
        "next_follow_up": 12
    }

    for field, new_value in updates.items():
        if field in field_map and new_value is not None:
            old_value = client.get(field, "")
            await update_client_field(
                row, field_map[field], str(new_value)
            )
            asyncio.create_task(log_audit(
                client_id, field,
                str(old_value), str(new_value),
                changed_by
            ))

    asyncio.create_task(log_activity(
        client_id, "CLIENT_UPDATED",
        f"Updated: {', '.join(updates.keys())}",
        "SUCCESS", ""
    ))

    return await get_client_by_id(client_id)


async def update_stage(
    client_id: str,
    stage: str,
    changed_by: str = "api"
) -> dict:
    client = await require_client(client_id)
    old_stage = client["stage"]

    await update_client_field(client["row_number"], 9, stage)

    asyncio.create_task(log_audit(
        client_id, "stage", old_stage, stage, changed_by
    ))
    asyncio.create_task(log_activity(
        client_id, "STAGE_UPDATED",
        f"Stage: {old_stage} → {stage}",
        "SUCCESS", ""
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
    client = await require_client(client_id)
    old_date = client.get("next_follow_up", "")

    await update_client_field(
        client["row_number"], 12, follow_up_date
    )

    asyncio.create_task(log_audit(
        client_id, "next_follow_up",
        old_date, follow_up_date, "api"
    ))
    asyncio.create_task(log_activity(
        client_id, "FOLLOWUP_UPDATED",
        f"Follow-up set to {follow_up_date}",
        "SUCCESS", ""
    ))

    return {
        "client_id": client_id,
        "previous_follow_up": old_date,
        "next_follow_up": follow_up_date
    }


# ── Delete / Archive / Restore ─────────────────────────

async def archive_client(client_id: str) -> dict:
    client = await require_client(client_id)

    if client.get("archived") == "Yes":
        raise ValueError(
            f"Client {client_id} is already archived"
        )

    await update_client_field(client["row_number"], 14, "Yes")

    asyncio.create_task(log_audit(
        client_id, "archived", "No", "Yes", "api"
    ))
    asyncio.create_task(log_activity(
        client_id, "CLIENT_ARCHIVED",
        f"Archived client {client['name']}",
        "SUCCESS", ""
    ))

    return {"client_id": client_id, "archived": True}


def _restore_client_sync(client_id: str) -> dict:
    spreadsheet = _get_spreadsheet_sync()
    sheet = spreadsheet.worksheet("Clients")
    records = sheet.get_all_records()

    for i, r in enumerate(records):
        if r.get("Client ID") == client_id:
            if r.get("Archived") != "Yes":
                raise ValueError(
                    f"Client {client_id} is not archived"
                )
            sheet.update_cell(i + 2, 14, "No")
            return {
                "client_id": client_id,
                "name": r.get("Name"),
                "restored": True
            }

    raise ValueError(f"Client not found: {client_id}")


async def restore_client(client_id: str) -> dict:
    result = await _run(_restore_client_sync, client_id)

    asyncio.create_task(log_audit(
        client_id, "archived", "Yes", "No", "api"
    ))
    asyncio.create_task(log_activity(
        client_id, "CLIENT_RESTORED",
        f"Restored client {result.get('name')}",
        "SUCCESS", ""
    ))

    return result


def _delete_client_sync(client_id: str) -> dict:
    spreadsheet = _get_spreadsheet_sync()
    sheet = spreadsheet.worksheet("Clients")
    records = sheet.get_all_records()

    for i, r in enumerate(records):
        if r.get("Client ID") == client_id:
            sheet.delete_rows(i + 2)
            return {
                "client_id": client_id,
                "deleted": True,
                "name": r.get("Name")
            }

    raise ValueError(f"Client not found: {client_id}")


async def delete_client_permanently(client_id: str) -> dict:
    result = await _run(_delete_client_sync, client_id)

    asyncio.create_task(log_activity(
        client_id, "CLIENT_DELETED",
        f"Permanently deleted {result.get('name')}",
        "SUCCESS", ""
    ))

    return result


async def get_archived_clients() -> List[dict]:
    records = await _get_all_records()
    return [
        _row_to_client(r, i)
        for i, r in enumerate(records)
        if r.get("Archived") == "Yes"
    ]


# ── Bulk Operations ────────────────────────────────────

async def bulk_update_stage(
    client_ids: List[str],
    stage: str
) -> dict:
    results = []
    errors = []

    for client_id in client_ids:
        try:
            result = await update_stage(client_id, stage)
            results.append(result)
        except Exception as e:
            errors.append({
                "client_id": client_id,
                "error": str(e)
            })

    return {
        "updated": len(results),
        "failed": len(errors),
        "results": results,
        "errors": errors
    }


async def bulk_archive(client_ids: List[str]) -> dict:
    results = []
    errors = []

    for client_id in client_ids:
        try:
            result = await archive_client(client_id)
            results.append(result)
        except Exception as e:
            errors.append({
                "client_id": client_id,
                "error": str(e)
            })

    return {
        "archived": len(results),
        "failed": len(errors),
        "results": results,
        "errors": errors
    }


# ── Rollback ───────────────────────────────────────────

def _get_audit_records_sync(client_id: str) -> List[dict]:
    spreadsheet = _get_spreadsheet_sync()
    sheet = spreadsheet.worksheet("Audit Log")
    records = sheet.get_all_records()
    return [
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


async def get_client_audit_history(
    client_id: str
) -> List[dict]:
    return await _run(_get_audit_records_sync, client_id)


async def rollback_client_field(
    client_id: str,
    field: str
) -> dict:
    history = await get_client_audit_history(client_id)
    field_history = [h for h in history if h["field"] == field]

    if not field_history:
        raise ValueError(
            f"No history for field '{field}' "
            f"on client {client_id}"
        )

    last_change = field_history[-1]
    old_value = last_change["old_value"]

    field_map = {
        "name": 3, "company": 4, "email": 5,
        "phone": 6, "service": 7, "priority": 8,
        "stage": 9, "notes": 13,
        "next_follow_up": 12, "archived": 14
    }

    if field not in field_map:
        raise ValueError(f"Cannot rollback field: {field}")

    client = await require_client(client_id)
    current_value = client.get(field, "")

    await update_client_field(
        client["row_number"],
        field_map[field],
        old_value
    )

    asyncio.create_task(log_audit(
        client_id, field,
        current_value, old_value, "rollback"
    ))
    asyncio.create_task(log_activity(
        client_id, "FIELD_ROLLED_BACK",
        f"Rolled back '{field}': {current_value} → {old_value}",
        "SUCCESS", ""
    ))

    return {
        "client_id": client_id,
        "field": field,
        "rolled_back_from": current_value,
        "rolled_back_to": old_value
    }


async def rollback_last_change(client_id: str) -> dict:
    history = await get_client_audit_history(client_id)

    if not history:
        raise ValueError(
            f"No change history for client {client_id}"
        )

    last_change = history[-1]
    return await rollback_client_field(
        client_id, last_change["field"]
    )


# ── Follow-ups ─────────────────────────────────────────

async def get_followups_due() -> List[dict]:
    today = date.today().isoformat()
    clients = await get_all_clients(limit=1000)

    return [
        c for c in clients
        if c.get("next_follow_up")
        and c["next_follow_up"] <= today
        and c.get("stage") not in ["Won", "Lost"]
    ]


# ── Pipeline ───────────────────────────────────────────

async def get_pipeline_summary() -> dict:
    clients = await get_all_clients(limit=1000)

    stages = [
        "New", "Contacted",
        "Consultation Scheduled",
        "Proposal Sent", "Won", "Lost"
    ]

    stage_counts = {s: 0 for s in stages}
    for c in clients:
        stage = c.get("stage", "New")
        stage_counts[stage] = stage_counts.get(stage, 0) + 1

    high_priority = [
        c for c in clients
        if c.get("priority") == "High"
        and c.get("stage") not in ["Won", "Lost"]
    ]

    won = [c for c in clients if c.get("stage") == "Won"]
    lost = [c for c in clients if c.get("stage") == "Lost"]

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
    spreadsheet = _get_spreadsheet_sync()
    sheet = spreadsheet.worksheet("Activities")
    sheet.append_row([
        "ACT-" + str(uuid.uuid4())[:8].upper(),
        client_id,
        datetime.utcnow().isoformat(),
        activity_type,
        description,
        result,
        resource_url
    ])


async def log_activity(
    client_id: str,
    activity_type: str,
    description: str,
    result: str,
    resource_url: str
):
    try:
        await _run(
            _log_activity_sync,
            client_id, activity_type,
            description, result, resource_url
        )
    except Exception as e:
        logger.error(f"Failed to log activity: {e}")


async def get_client_activities(
    client_id: str
) -> List[dict]:
    def _sync():
        spreadsheet = _get_spreadsheet_sync()
        sheet = spreadsheet.worksheet("Activities")
        records = sheet.get_all_records()
        return [
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
    return await _run(_sync)


async def search_activities(
    activity_type: Optional[str] = None,
    client_id: Optional[str] = None,
    limit: int = 50
) -> List[dict]:
    def _sync():
        spreadsheet = _get_spreadsheet_sync()
        sheet = spreadsheet.worksheet("Activities")
        records = sheet.get_all_records()
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
            if (not client_id or
                r.get("Client ID") == client_id)
            and (not activity_type or
                 r.get("Type") == activity_type)
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
    spreadsheet = _get_spreadsheet_sync()
    sheet = spreadsheet.worksheet("Audit Log")
    sheet.append_row([
        "AUD-" + str(uuid.uuid4())[:8].upper(),
        client_id,
        datetime.utcnow().isoformat(),
        field,
        old_value,
        new_value,
        changed_by
    ])


async def log_audit(
    client_id: str,
    field: str,
    old_value: str,
    new_value: str,
    changed_by: str
):
    try:
        await _run(
            _log_audit_sync,
            client_id, field,
            old_value, new_value, changed_by
        )
    except Exception as e:
        logger.error(f"Failed to log audit: {e}")


# ── Agent Logs ─────────────────────────────────────────

def _log_agent_sync(
    log_type: str,
    input_text: str,
    output_text: str,
    error: str
):
    spreadsheet = _get_spreadsheet_sync()
    sheet = spreadsheet.worksheet("Agent Logs")
    sheet.append_row([
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
    try:
        await _run(
            _log_agent_sync,
            log_type, input_text, output_text, error
        )
    except Exception as e:
        logger.error(f"Failed to log agent: {e}")