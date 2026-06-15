import gspread
from google.oauth2.service_account import Credentials
from typing import Optional
import uuid
from datetime import datetime
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

def get_sheets_client():
    creds = Credentials.from_service_account_file(
        "credentials.json",
        scopes=SCOPES
    )
    return gspread.authorize(creds)

def get_spreadsheet():
    settings = get_settings()
    client = get_sheets_client()
    return client.open_by_key(settings.spreadsheet_id)

def setup_sheets():
    """Create all required sheets with headers"""
    spreadsheet = get_spreadsheet()
    existing = [s.title for s in spreadsheet.worksheets()]

    sheets_config = {
        "Clients": CLIENT_HEADERS,
        "Activities": ACTIVITY_HEADERS,
        "Agent Logs": ["Log ID", "Timestamp", "Type", "Input", "Output", "Error"]
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
            logger.info(f"Sheet already exists: {sheet_name}")

async def create_client(data: dict) -> dict:
    spreadsheet = get_spreadsheet()
    sheet = spreadsheet.worksheet("Clients")

    all_records = sheet.get_all_records()

    if data.get("email"):
        duplicate = next(
            (r for r in all_records
             if r.get("Email", "").lower() == data["email"].lower()
             and r.get("Archived", "") != "Yes"),
            None
        )
        if duplicate:
            raise ValueError(
                f"Client with email already exists: {duplicate['Client ID']}"
            )

    client_id = "CL-" + str(uuid.uuid4())[:8].upper()
    now = datetime.utcnow().isoformat()

    row = [
        client_id, now,
        data.get("name", ""),
        data.get("company", ""),
        data.get("email", ""),
        data.get("phone", ""),
        data.get("service", ""),
        data.get("priority", "Medium"),
        data.get("stage", "New"),
        "", "", "",
        data.get("notes", ""),
        "No"
    ]

    sheet.append_row(row)

    await log_activity(
        client_id,
        "CLIENT_CREATED",
        f"Created client record for {data.get('name')}",
        "SUCCESS",
        ""
    )

    logger.info(f"Created client: {client_id}")

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
        "notes": data.get("notes")
    }

async def get_all_clients(
    query: Optional[str] = None,
    stage: Optional[str] = None,
    priority: Optional[str] = None,
    client_id: Optional[str] = None,
    email: Optional[str] = None,
    limit: int = 20
) -> list:
    spreadsheet = get_spreadsheet()
    sheet = spreadsheet.worksheet("Clients")
    records = sheet.get_all_records()

    results = []
    for i, r in enumerate(records):
        if r.get("Archived") == "Yes":
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
            searchable = " ".join(str(v) for v in r.values()).lower()
            if query.lower() not in searchable:
                continue

        results.append({
            "row_number": i + 2,
            "client_id": r.get("Client ID"),
            "created_at": r.get("Created At"),
            "name": r.get("Name"),
            "company": r.get("Company"),
            "email": r.get("Email"),
            "phone": r.get("Phone"),
            "service": r.get("Service"),
            "priority": r.get("Priority"),
            "stage": r.get("Stage"),
            "folder_url": r.get("Folder URL"),
            "report_url": r.get("Report URL"),
            "next_follow_up": r.get("Next Follow-up"),
            "notes": r.get("Notes")
        })

    return list(reversed(results))[:limit]

async def get_client_by_id(client_id: str) -> Optional[dict]:
    clients = await get_all_clients(client_id=client_id, limit=1)
    return clients[0] if clients else None

async def require_client(client_id: str) -> dict:
    client = await get_client_by_id(client_id)
    if not client:
        raise ValueError(f"Client not found: {client_id}")
    return client

async def update_client_field(
    row_number: int,
    col: int,
    value: str
):
    spreadsheet = get_spreadsheet()
    sheet = spreadsheet.worksheet("Clients")
    sheet.update_cell(row_number, col, value)

async def update_client(
    client_id: str,
    updates: dict
) -> dict:
    client = await require_client(client_id)
    row = client["row_number"]

    field_map = {
        "name": 3,
        "company": 4,
        "email": 5,
        "phone": 6,
        "service": 7,
        "priority": 8,
        "stage": 9,
        "notes": 13
    }

    for field, value in updates.items():
        if field in field_map and value is not None:
            await update_client_field(row, field_map[field], str(value))

    await log_activity(
        client_id,
        "CLIENT_UPDATED",
        f"Updated fields: {', '.join(updates.keys())}",
        "SUCCESS",
        ""
    )

    return await get_client_by_id(client_id)

async def update_stage(client_id: str, stage: str) -> dict:
    client = await require_client(client_id)
    old_stage = client["stage"]
    await update_client_field(client["row_number"], 9, stage)

    await log_activity(
        client_id,
        "STAGE_UPDATED",
        f"Stage changed from {old_stage} to {stage}",
        "SUCCESS",
        ""
    )

    return {
        "client_id": client_id,
        "previous_stage": old_stage,
        "new_stage": stage
    }

async def archive_client(client_id: str) -> dict:
    client = await require_client(client_id)
    await update_client_field(client["row_number"], 14, "Yes")

    await log_activity(
        client_id,
        "CLIENT_ARCHIVED",
        f"Archived client {client['name']}",
        "SUCCESS",
        ""
    )

    return {"client_id": client_id, "archived": True}

async def get_pipeline_summary() -> dict:
    clients = await get_all_clients(limit=1000)

    stages = [
        "New", "Contacted", "Consultation Scheduled",
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

    return {
        "total_clients": len(clients),
        "stage_counts": stage_counts,
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

async def log_activity(
    client_id: str,
    activity_type: str,
    description: str,
    result: str,
    resource_url: str
):
    try:
        spreadsheet = get_spreadsheet()
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
    except Exception as e:
        logger.error(f"Failed to log activity: {e}")

async def get_client_activities(client_id: str) -> list:
    spreadsheet = get_spreadsheet()
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

async def log_agent(
    log_type: str,
    input_text: str,
    output_text: str,
    error: str = ""
):
    try:
        spreadsheet = get_spreadsheet()
        sheet = spreadsheet.worksheet("Agent Logs")
        sheet.append_row([
            "LOG-" + str(uuid.uuid4())[:8].upper(),
            datetime.utcnow().isoformat(),
            log_type,
            input_text[:500],
            output_text[:500],
            error[:200]
        ])
    except Exception as e:
        logger.error(f"Failed to log agent: {e}")