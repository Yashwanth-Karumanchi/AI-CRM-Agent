import json
import re
import asyncio
from typing import Optional

from fastapi import (
    FastAPI, Depends, UploadFile,
    File, HTTPException, Query, Form
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (
    StreamingResponse, FileResponse, Response
)
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest

from app.auth import verify_credentials
from app.config import get_settings
from app.logger import get_logger
from app.services import sheets
from app.services.llm import generate, generate_json

from app.models import (
    ClientCreate, ClientUpdate, StageUpdate,
    EmailDraft, EmailSend, AgentChat,
    AgentDraftEmail, BulkStageUpdate,
    BulkArchive, FollowUpUpdate, DeleteDraftInput,
    NLSearchInput, SmartFilterInput,
    ScheduleMeetingInput, UpdateMeetingInput,
    MeetingNotesInput, GenerateContractInput,
    GenerateInvoiceInput, GenerateProposalInput,
    TimelineItem, LineItem, PricingTier
)

from app.agent import (
    extract_client_from_pdf,
    analyze_client,
    analyze_document_content,
    draft_email,
    chat,
    score_single_client,
    score_entire_pipeline,
    find_similar_clients,
    get_daily_recommendations,
    nl_search,
    pipeline_patterns,
    smart_filter,
    forecast_revenue,
    analyze_win_loss
)

from app.services.document import (
    generate_client_report,
    generate_pipeline_report
)
from app.services.pdf import extract_pdf_text
from app.services.gmail import (
    send_email, create_draft,
    delete_draft, list_drafts
)
from app.services.calendar import (
    schedule_meeting,
    get_upcoming_meetings,
    get_meeting,
    update_meeting,
    cancel_meeting,
    add_meeting_notes,
    get_client_meetings
)
from app.services.contracts import (
    generate_contract,
    generate_invoice,
    generate_proposal
)
from app.services.reports import (
    generate_weekly_report,
    generate_monthly_report,
    generate_client_acquisition_report,
    generate_agent_activity_report
)

logger = get_logger(__name__)

# ── App ────────────────────────────────────────────────

app = FastAPI(
    title="AI CRM Agent — ARIA",
    description=(
        "Production-ready AI CRM with ARIA frontend.\n\n"
        "## Features\n"
        "- Full client CRUD with audit trail and rollback\n"
        "- PDF extraction with AI client creation\n"
        "- Word documents: reports, contracts, invoices, proposals\n"
        "- Gmail send and draft management\n"
        "- Google Calendar integration\n"
        "- ARIA AI chat with action execution\n"
        "- Pipeline intelligence and scoring\n"
        "- Natural language search\n"
        "- Revenue forecasting and win/loss analysis\n"
        "- Bulk import with SSE live streaming\n"
        "- File uploads in ARIA chat (PDF, Excel, CSV, Word)\n"
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# ── Middleware ─────────────────────────────────────────

class SuppressAuthPopupMiddleware(BaseHTTPMiddleware):
    """
    Prevents browser native Basic Auth popup by changing
    WWW-Authenticate to 'xBasic' for XHR requests on 401.
    The JS API module sends X-Requested-With on all calls.
    """
    async def dispatch(
        self,
        request: StarletteRequest,
        call_next
    ):
        response = await call_next(request)
        if (
            response.status_code == 401 and
            request.headers.get("X-Requested-With") ==
            "XMLHttpRequest"
        ):
            response.headers["WWW-Authenticate"] = \
                'xBasic realm="ARIA"'
        return response


app.add_middleware(SuppressAuthPopupMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# ── Static Files ───────────────────────────────────────

app.mount(
    "/static",
    StaticFiles(directory="app/static"),
    name="static"
)

# ── Startup ────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    logger.info("ARIA CRM Agent starting up")
    try:
        sheets.setup_sheets()
        logger.info("Google Sheets initialized")
    except Exception as e:
        logger.error(f"Sheets setup failed: {e}")
        logger.info("Continuing without Sheets — will retry on first request")


# ── System ─────────────────────────────────────────────

@app.get("/health", tags=["System"])
async def health():
    return {
        "ok": True,
        "service": "ARIA AI CRM Agent",
        "version": "2.0.0"
    }


@app.post("/cache/clear", tags=["System"])
async def clear_cache(
    username: str = Depends(verify_credentials)
):
    """Force clear the server-side spreadsheet cache"""
    sheets._cache_clear()
    return {"ok": True, "message": "Cache cleared"}


@app.get("/debug-gmail", tags=["System"])
async def debug_gmail():
    import os
    token_env = os.getenv("GMAIL_TOKEN")
    return {
        "gmail_token_exists": token_env is not None,
        "gmail_token_length": len(token_env) if token_env else 0,
        "gmail_address": os.getenv("GMAIL_ADDRESS"),
        "has_refresh_token": "refresh_token" in (token_env or "")
    }


# ── ARIA Pages ─────────────────────────────────────────

@app.get("/aria",          tags=["ARIA Pages"])
@app.get("/aria/",         tags=["ARIA Pages"])
async def aria_index():
    return FileResponse("app/static/pages/index.html")


@app.get("/aria/dashboard", tags=["ARIA Pages"])
async def aria_dashboard():
    return FileResponse("app/static/pages/dashboard.html")


@app.get("/aria/clients",   tags=["ARIA Pages"])
async def aria_clients_page():
    return FileResponse("app/static/pages/clients.html")


@app.get("/aria/chat",      tags=["ARIA Pages"])
async def aria_chat_page():
    return FileResponse("app/static/pages/chat.html")


@app.get("/aria/calendar",  tags=["ARIA Pages"])
async def aria_calendar_page():
    return FileResponse("app/static/pages/calendar.html")


@app.get("/aria/email",     tags=["ARIA Pages"])
async def aria_email_page():
    return FileResponse("app/static/pages/email.html")


@app.get("/aria/reports",   tags=["ARIA Pages"])
async def aria_reports_page():
    return FileResponse("app/static/pages/reports.html")


@app.get("/aria/intel",     tags=["ARIA Pages"])
async def aria_intel_page():
    return FileResponse("app/static/pages/intel.html")


@app.get("/aria/search",    tags=["ARIA Pages"])
async def aria_search_page():
    return FileResponse("app/static/pages/search.html")


@app.get("/aria/import",    tags=["ARIA Pages"])
async def aria_import_page():
    return FileResponse("app/static/pages/import.html")


# ── Clients: CRUD ──────────────────────────────────────

@app.post("/clients", tags=["Clients"])
async def create_client(
    data: ClientCreate,
    username: str = Depends(verify_credentials)
):
    """Create a new client"""
    try:
        client = await sheets.create_client(data.model_dump())
        return {"ok": True, "message": "Client created", "client": client}
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/clients/archived", tags=["Clients"])
async def get_archived_clients(
    username: str = Depends(verify_credentials)
):
    """Get all archived clients"""
    clients = await sheets.get_archived_clients()
    return {"ok": True, "count": len(clients), "clients": clients}


@app.get("/clients", tags=["Clients"])
async def list_clients(
    query:            Optional[str]  = Query(None),
    stage:            Optional[str]  = Query(None),
    priority:         Optional[str]  = Query(None),
    client_id:        Optional[str]  = Query(None),
    email:            Optional[str]  = Query(None),
    include_archived: bool           = Query(False),
    limit:            int            = Query(20, ge=1, le=500),
    username:         str            = Depends(verify_credentials)
):
    """Search and filter clients"""
    clients = await sheets.get_all_clients(
        query=query, stage=stage, priority=priority,
        client_id=client_id, email=email,
        include_archived=include_archived, limit=limit
    )
    return {"ok": True, "count": len(clients), "clients": clients}


@app.get("/clients/{client_id}", tags=["Clients"])
async def get_client(
    client_id: str,
    username:  str = Depends(verify_credentials)
):
    """Get a single client by ID"""
    try:
        client = await sheets.require_client(client_id)
        return {"ok": True, "client": client}
    except ValueError as e:
        raise HTTPException(404, str(e))


@app.put("/clients/{client_id}", tags=["Clients"])
async def update_client(
    client_id: str,
    data:      ClientUpdate,
    username:  str = Depends(verify_credentials)
):
    """Update client fields"""
    try:
        updates = data.model_dump(exclude_none=True)
        if not updates:
            raise HTTPException(400, "No fields to update")
        client = await sheets.update_client(
            client_id, updates, changed_by=username
        )
        return {
            "ok": True,
            "message": "Client updated",
            "client": client
        }
    except ValueError as e:
        raise HTTPException(404, str(e))


@app.put("/clients/{client_id}/stage", tags=["Clients"])
async def update_stage(
    client_id: str,
    data:      StageUpdate,
    username:  str = Depends(verify_credentials)
):
    """Update pipeline stage"""
    try:
        result = await sheets.update_stage(
            client_id, data.stage.value, changed_by=username
        )
        return {
            "ok": True,
            "message": "Stage updated",
            **result
        }
    except ValueError as e:
        raise HTTPException(404, str(e))


@app.put("/clients/{client_id}/followup", tags=["Clients"])
async def update_followup(
    client_id: str,
    data:      FollowUpUpdate,
    username:  str = Depends(verify_credentials)
):
    """Set next follow-up date"""
    try:
        result = await sheets.update_next_followup(
            client_id, data.follow_up_date
        )
        return {
            "ok": True,
            "message": "Follow-up updated",
            **result
        }
    except ValueError as e:
        raise HTTPException(404, str(e))


@app.delete("/clients/{client_id}", tags=["Clients"])
async def archive_client(
    client_id: str,
    username:  str = Depends(verify_credentials)
):
    """Soft-delete: archive a client"""
    try:
        result = await sheets.archive_client(client_id)
        return {
            "ok": True,
            "message": "Client archived",
            **result
        }
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/clients/{client_id}/restore", tags=["Clients"])
async def restore_archived_client(
    client_id: str,
    username:  str = Depends(verify_credentials)
):
    """Restore an archived client"""
    try:
        result = await sheets.restore_client(client_id)
        return {
            "ok": True,
            "message": "Client restored",
            **result
        }
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.delete("/clients/{client_id}/permanent", tags=["Clients"])
async def delete_permanently(
    client_id: str,
    username:  str = Depends(verify_credentials)
):
    """Permanently delete a client (1-hour undo via ARIA chat)"""
    try:
        result = await sheets.delete_client_permanently(client_id)
        return {
            "ok": True,
            "message": "Client permanently deleted",
            **result
        }
    except ValueError as e:
        raise HTTPException(404, str(e))


@app.post("/clients/restore-deleted", tags=["Clients"])
async def restore_deleted_client_endpoint(
    client_id: Optional[str] = None,
    username:  str           = Depends(verify_credentials)
):
    """
    Restore the last permanently deleted client.
    Pass client_id to restore a specific one.
    Undo window: 1 hour from deletion.
    """
    try:
        result = await sheets.restore_deleted_client(client_id)
        return {
            "ok": True,
            "message": f"Restored: {result['name']}",
            **result
        }
    except ValueError as e:
        raise HTTPException(400, str(e))


# ── Bulk Operations ────────────────────────────────────

@app.post("/clients/bulk/stage", tags=["Bulk"])
async def bulk_update_stage(
    data:     BulkStageUpdate,
    username: str = Depends(verify_credentials)
):
    """Update stage for multiple clients"""
    result = await sheets.bulk_update_stage(
        data.client_ids, data.stage.value
    )
    return {"ok": True, **result}


@app.post("/clients/bulk/archive", tags=["Bulk"])
async def bulk_archive(
    data:     BulkArchive,
    username: str = Depends(verify_credentials)
):
    """Archive multiple clients"""
    result = await sheets.bulk_archive(data.client_ids)
    return {"ok": True, **result}


@app.post("/clients/import/preview", tags=["Bulk"])
async def preview_import(
    file:     UploadFile = File(...),
    username: str        = Depends(verify_credentials)
):
    """
    Preview an Excel/CSV file before importing.
    Returns column names, row count, sample rows,
    and validation errors — creates nothing.
    """
    try:
        from app.services.importer import parse_excel, parse_csv

        file_bytes = await file.read()
        name       = (file.filename or "").lower()

        if name.endswith((".xlsx", ".xls")):
            rows, cols, errors = parse_excel(file_bytes)
        elif name.endswith(".csv"):
            rows, cols, errors = parse_csv(file_bytes)
        else:
            raise HTTPException(
                400, "File must be .xlsx, .xls, or .csv"
            )

        return {
            "ok":               True,
            "filename":         file.filename,
            "total_valid_rows": len(rows),
            "detected_columns": cols,
            "validation_errors": errors,
            "sample_rows":      rows[:5],
            "ready_to_import":  len(rows) > 0
        }

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"Preview failed: {e}")
        raise HTTPException(500, str(e))


@app.post("/clients/import", tags=["Bulk"])
async def bulk_import(
    file:             UploadFile = File(...),
    check_duplicates: bool       = Query(True),
    username:         str        = Depends(verify_credentials)
):
    """Import clients from Excel or CSV"""
    try:
        from app.services.importer import (
            parse_excel, parse_csv, bulk_import_clients
        )

        file_bytes = await file.read()
        name       = (file.filename or "").lower()

        if name.endswith((".xlsx", ".xls")):
            rows, cols, parse_errors = parse_excel(file_bytes)
        elif name.endswith(".csv"):
            rows, cols, parse_errors = parse_csv(file_bytes)
        else:
            raise HTTPException(
                400, "File must be .xlsx, .xls, or .csv"
            )

        if not rows:
            return {
                "ok": False,
                "message": "No valid rows to import",
                "parse_errors": parse_errors
            }

        result = await bulk_import_clients(
            rows, sheets,
            check_duplicates=check_duplicates
        )

        asyncio.create_task(sheets.log_agent(
            "BULK_IMPORT",
            f"File: {file.filename}",
            f"Imported: {result['imported']} | "
            f"Skipped: {result['skipped']} | "
            f"Failed: {result['failed']}"
        ))

        return {
            "ok":          True,
            "filename":    file.filename,
            "parse_errors": parse_errors,
            **result
        }

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"Bulk import failed: {e}")
        raise HTTPException(500, str(e))


@app.post("/clients/import/stream", tags=["Bulk"])
async def bulk_import_stream(
    file:             UploadFile = File(...),
    check_duplicates: bool       = Query(True),
    username:         str        = Depends(verify_credentials)
):
    """
    Import with live SSE progress stream.
    Client reads stream line-by-line for real-time updates.
    """
    from app.services.importer import (
        parse_excel, parse_csv,
        bulk_import_clients_stream
    )

    file_bytes = await file.read()
    name       = (file.filename or "").lower()

    try:
        if name.endswith((".xlsx", ".xls")):
            rows, cols, _ = parse_excel(file_bytes)
        elif name.endswith(".csv"):
            rows, cols, _ = parse_csv(file_bytes)
        else:
            raise HTTPException(
                400, "File must be .xlsx or .csv"
            )
    except ValueError as e:
        raise HTTPException(400, str(e))

    async def event_stream():
        async for event in bulk_import_clients_stream(
            rows, sheets,
            check_duplicates=check_duplicates
        ):
            yield f"data: {json.dumps(event)}\n\n"
        yield 'data: {"type":"done"}\n\n'

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":       "no-cache",
            "X-Accel-Buffering":   "no",
            "Access-Control-Allow-Origin": "*"
        }
    )


# ── Audit & Rollback ───────────────────────────────────

@app.get("/clients/{client_id}/audit", tags=["Audit"])
async def get_audit_history(
    client_id: str,
    username:  str = Depends(verify_credentials)
):
    """Get full audit trail for a client"""
    try:
        await sheets.require_client(client_id)
        history = await sheets.get_client_audit_history(client_id)
        return {
            "ok":        True,
            "client_id": client_id,
            "count":     len(history),
            "history":   history
        }
    except ValueError as e:
        raise HTTPException(404, str(e))


@app.post("/clients/{client_id}/rollback", tags=["Audit"])
async def rollback_last_change(
    client_id: str,
    username:  str = Depends(verify_credentials)
):
    """Undo the last change made to a client"""
    try:
        result = await sheets.rollback_last_change(client_id)
        return {
            "ok":      True,
            "message": "Last change rolled back",
            **result
        }
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post(
    "/clients/{client_id}/rollback/{field}",
    tags=["Audit"]
)
async def rollback_field(
    client_id: str,
    field:     str,
    username:  str = Depends(verify_credentials)
):
    """Rollback a specific field to its previous value"""
    try:
        result = await sheets.rollback_client_field(
            client_id, field
        )
        return {
            "ok":      True,
            "message": f"Field '{field}' rolled back",
            **result
        }
    except ValueError as e:
        raise HTTPException(400, str(e))


# ── Activities ─────────────────────────────────────────

@app.get("/clients/{client_id}/activity", tags=["Activities"])
async def get_client_activity(
    client_id: str,
    username:  str = Depends(verify_credentials)
):
    """Get activity timeline for a client"""
    try:
        await sheets.require_client(client_id)
        activities = await sheets.get_client_activities(client_id)
        return {
            "ok":         True,
            "client_id":  client_id,
            "count":      len(activities),
            "activities": activities
        }
    except ValueError as e:
        raise HTTPException(404, str(e))


@app.get("/activities", tags=["Activities"])
async def search_activities(
    activity_type: Optional[str] = Query(None),
    client_id:     Optional[str] = Query(None),
    limit:         int           = Query(50, ge=1, le=200),
    username:      str           = Depends(verify_credentials)
):
    """Search all activities"""
    activities = await sheets.search_activities(
        activity_type=activity_type,
        client_id=client_id,
        limit=limit
    )
    return {
        "ok":         True,
        "count":      len(activities),
        "activities": activities
    }


# ── Pipeline ───────────────────────────────────────────

@app.get("/pipeline", tags=["Pipeline"])
async def get_pipeline(
    username: str = Depends(verify_credentials)
):
    """Get pipeline summary"""
    summary = await sheets.get_pipeline_summary()
    return {"ok": True, **summary}


@app.get("/pipeline/report", tags=["Pipeline"])
async def pipeline_report(
    username: str = Depends(verify_credentials)
):
    """Download pipeline summary as Word document"""
    summary      = await sheets.get_pipeline_summary()
    clients      = await sheets.get_all_clients(limit=1000)
    report_bytes = generate_pipeline_report(summary, clients)
    return Response(
        content=report_bytes,
        media_type=(
            "application/vnd.openxmlformats-officedocument"
            ".wordprocessingml.document"
        ),
        headers={
            "Content-Disposition":
                "attachment; filename=pipeline_report.docx"
        }
    )


@app.get("/followups/due", tags=["Pipeline"])
async def followups_due(
    username: str = Depends(verify_credentials)
):
    """Get clients with follow-ups due today or overdue"""
    clients = await sheets.get_followups_due()
    return {
        "ok":      True,
        "count":   len(clients),
        "clients": clients
    }


# ── Documents ──────────────────────────────────────────

@app.post("/process-pdf", tags=["Documents"])
async def process_pdf(
    file:     UploadFile = File(...),
    username: str        = Depends(verify_credentials)
):
    """Upload PDF → AI extracts client data → creates client"""
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(400, "File must be a PDF")
    try:
        file_bytes = await file.read()
        pdf_data   = extract_pdf_text(file_bytes)
        if not pdf_data["raw_text"].strip():
            raise HTTPException(
                400, "Could not extract text from PDF. "
                     "File may be scanned or image-based."
            )
        extracted = await extract_client_from_pdf(
            pdf_data["raw_text"]
        )
        client = await sheets.create_client(extracted)
        asyncio.create_task(sheets.log_activity(
            client["client_id"], "PDF_PROCESSED",
            f"Created from PDF: {file.filename}",
            "SUCCESS", ""
        ))
        return {
            "ok":              True,
            "message":         "PDF processed and client created",
            "filename":        file.filename,
            "pages_processed": pdf_data["page_count"],
            "client":          client,
            "extracted_data":  extracted
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"PDF processing failed: {e}")
        raise HTTPException(500, f"PDF processing failed: {e}")


@app.post("/clients/{client_id}/report", tags=["Documents"])
async def generate_report(
    client_id: str,
    username:  str = Depends(verify_credentials)
):
    """Generate Word document client report"""
    try:
        client       = await sheets.require_client(client_id)
        analysis     = await analyze_client(client)
        report_bytes = generate_client_report(client, analysis)
        asyncio.create_task(sheets.log_activity(
            client_id, "REPORT_GENERATED",
            f"Report for {client['name']}", "SUCCESS", ""
        ))
        return Response(
            content=report_bytes,
            media_type=(
                "application/vnd.openxmlformats-officedocument"
                ".wordprocessingml.document"
            ),
            headers={
                "Content-Disposition":
                    f"attachment; filename=report_{client_id}.docx"
            }
        )
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        logger.error(f"Report failed: {e}")
        raise HTTPException(500, str(e))


# ── Email ──────────────────────────────────────────────

@app.post("/email/draft", tags=["Email"])
async def create_email_draft(
    data:     EmailDraft,
    username: str = Depends(verify_credentials)
):
    """Create a Gmail draft"""
    try:
        settings  = get_settings()
        client    = await sheets.require_client(data.client_id)
        recipient = str(data.to) if data.to else client.get("email")
        if not recipient:
            raise HTTPException(400, "No recipient email found")
        result = await create_draft(
            to=recipient,
            subject=data.subject,
            body=data.body,
            from_email=settings.gmail_address
        )
        asyncio.create_task(sheets.log_activity(
            data.client_id, "EMAIL_DRAFT_CREATED",
            f"Draft for {recipient}: {data.subject}",
            "SUCCESS", result.get("gmail_drafts_url", "")
        ))
        return {"ok": True, "message": "Draft created", **result}
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/email/send", tags=["Email"])
async def send_email_endpoint(
    data:     EmailSend,
    username: str = Depends(verify_credentials)
):
    """Send a real email via Gmail"""
    try:
        settings  = get_settings()
        client    = await sheets.require_client(data.client_id)
        recipient = str(data.to) if data.to else client.get("email")
        if not recipient:
            raise HTTPException(400, "No recipient email found")
        result = await send_email(
            to=recipient,
            subject=data.subject,
            body=data.body,
            from_email=settings.gmail_address
        )
        asyncio.create_task(sheets.log_activity(
            data.client_id, "EMAIL_SENT",
            f"Sent to {recipient}: {data.subject}",
            "SUCCESS", ""
        ))
        return {"ok": True, "message": "Email sent", **result}
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.delete("/email/draft/{draft_id}", tags=["Email"])
async def delete_email_draft(
    draft_id: str,
    username: str = Depends(verify_credentials)
):
    """Delete a Gmail draft"""
    try:
        result = await delete_draft(draft_id)
        return {"ok": True, "message": "Draft deleted", **result}
    except Exception as e:
        raise HTTPException(400, str(e))


@app.get("/email/drafts", tags=["Email"])
async def get_email_drafts(
    max_results: int = Query(10, ge=1, le=50),
    username:    str = Depends(verify_credentials)
):
    """List Gmail drafts"""
    try:
        drafts = await list_drafts(max_results)
        return {
            "ok":     True,
            "count":  len(drafts),
            "drafts": drafts
        }
    except Exception as e:
        raise HTTPException(400, str(e))


# ── AI Agent ───────────────────────────────────────────

@app.post("/agent/chat", tags=["Agent"])
async def agent_chat(
    data:     AgentChat,
    username: str = Depends(verify_credentials)
):
    """Ask AI anything about your CRM"""
    try:
        response = await chat(data.message, data.client_id)
        asyncio.create_task(
            sheets.log_agent("CHAT", data.message, response)
        )
        return {
            "ok":       True,
            "message":  data.message,
            "response": response
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/agent/analyze/{client_id}", tags=["Agent"])
async def agent_analyze(
    client_id: str,
    username:  str = Depends(verify_credentials)
):
    """Deep AI analysis of a client"""
    try:
        client   = await sheets.require_client(client_id)
        analysis = await analyze_client(client)
        asyncio.create_task(
            sheets.log_agent(
                "ANALYZE_CLIENT", client_id, str(analysis)
            )
        )
        return {
            "ok":          True,
            "client_id":   client_id,
            "client_name": client.get("name"),
            "analysis":    analysis
        }
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/agent/draft-email", tags=["Agent"])
async def agent_draft_email(
    data:     AgentDraftEmail,
    username: str = Depends(verify_credentials)
):
    """AI drafts a professional email and saves to Gmail"""
    try:
        settings  = get_settings()
        client    = await sheets.require_client(data.client_id)
        drafted   = await draft_email(client, data.instruction)
        recipient = client.get("email")
        if not recipient:
            raise HTTPException(400, "Client has no email address")

        if data.send:
            result = await send_email(
                to=recipient,
                subject=drafted["subject"],
                body=drafted["body"],
                from_email=settings.gmail_address
            )
            asyncio.create_task(sheets.log_activity(
                data.client_id, "AI_EMAIL_SENT",
                f"AI sent to {recipient}", "SUCCESS", ""
            ))
            return {
                "ok":       True,
                "message":  "AI email sent",
                "subject":  drafted["subject"],
                "body":     drafted["body"],
                "sent_to":  recipient,
                **result
            }
        else:
            result = await create_draft(
                to=recipient,
                subject=drafted["subject"],
                body=drafted["body"],
                from_email=settings.gmail_address
            )
            asyncio.create_task(sheets.log_activity(
                data.client_id, "AI_EMAIL_DRAFT",
                f"AI draft for {recipient}", "SUCCESS",
                result.get("gmail_drafts_url", "")
            ))
            return {
                "ok":      True,
                "message": "AI draft saved to Gmail",
                "subject": drafted["subject"],
                "body":    drafted["body"],
                **result
            }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Calendar ───────────────────────────────────────────

@app.post("/meetings", tags=["Calendar"])
async def create_meeting(
    data:     ScheduleMeetingInput,
    username: str = Depends(verify_credentials)
):
    """Schedule a meeting with a client"""
    try:
        client = await sheets.require_client(data.client_id)
        result = await schedule_meeting(
            client=client,
            title=data.title,
            start_time=data.start_time,
            end_time=data.end_time,
            description=data.description,
            location=data.location,
            invite_client=data.invite_client,
            meeting_notes=data.meeting_notes
        )
        asyncio.create_task(sheets.log_activity(
            data.client_id, "MEETING_SCHEDULED",
            f"Meeting: {result['title']} at {result['start_time']}",
            "SUCCESS", result.get("calendar_link", "")
        ))
        asyncio.create_task(sheets.update_next_followup(
            data.client_id, data.start_time[:10]
        ))
        return {
            "ok":        True,
            "message":   "Meeting scheduled",
            "client_id": data.client_id,
            **result
        }
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"Meeting failed: {e}")
        raise HTTPException(500, str(e))


@app.get("/meetings", tags=["Calendar"])
async def upcoming_meetings(
    days_ahead:  int = Query(7,  ge=1, le=90),
    max_results: int = Query(10, ge=1, le=50),
    username:    str = Depends(verify_credentials)
):
    """Get upcoming meetings"""
    try:
        meetings = await get_upcoming_meetings(
            days_ahead=days_ahead,
            max_results=max_results
        )
        return {
            "ok":      True,
            "count":   len(meetings),
            "meetings": meetings
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/meetings/{event_id}", tags=["Calendar"])
async def get_meeting_details(
    event_id: str,
    username: str = Depends(verify_credentials)
):
    """Get details of a specific meeting"""
    try:
        meeting = await get_meeting(event_id)
        return {"ok": True, "meeting": meeting}
    except Exception as e:
        raise HTTPException(404, str(e))


@app.put("/meetings/{event_id}", tags=["Calendar"])
async def update_meeting_endpoint(
    event_id: str,
    data:     UpdateMeetingInput,
    username: str = Depends(verify_credentials)
):
    """Update an existing meeting"""
    try:
        result = await update_meeting(
            event_id=event_id,
            title=data.title,
            start_time=data.start_time,
            end_time=data.end_time,
            description=data.description,
            location=data.location,
            meeting_notes=data.meeting_notes
        )
        return {"ok": True, "message": "Meeting updated", **result}
    except Exception as e:
        raise HTTPException(400, str(e))


@app.delete("/meetings/{event_id}", tags=["Calendar"])
async def cancel_meeting_endpoint(
    event_id:         str,
    notify_attendees: bool = Query(True),
    username:         str  = Depends(verify_credentials)
):
    """Cancel a meeting"""
    try:
        result = await cancel_meeting(
            event_id=event_id,
            notify_attendees=notify_attendees
        )
        return {"ok": True, "message": "Meeting cancelled", **result}
    except Exception as e:
        raise HTTPException(400, str(e))


@app.post("/meetings/{event_id}/notes", tags=["Calendar"])
async def add_notes_to_meeting(
    event_id: str,
    data:     MeetingNotesInput,
    username: str = Depends(verify_credentials)
):
    """Add notes to an existing meeting"""
    try:
        result = await add_meeting_notes(event_id, data.notes)
        return {
            "ok":      True,
            "message": "Notes added",
            **result
        }
    except Exception as e:
        raise HTTPException(400, str(e))


@app.get("/clients/{client_id}/meetings", tags=["Calendar"])
async def get_meetings_for_client(
    client_id:  str,
    days_back:  int = Query(30, ge=0, le=365),
    days_ahead: int = Query(30, ge=0, le=365),
    username:   str = Depends(verify_credentials)
):
    """Get all meetings for a client"""
    try:
        client = await sheets.require_client(client_id)
        if not client.get("email"):
            raise HTTPException(
                400, "Client has no email — cannot search calendar"
            )
        meetings = await get_client_meetings(
            client_email=client["email"],
            days_back=days_back,
            days_ahead=days_ahead
        )
        return {
            "ok":        True,
            "client_id": client_id,
            "count":     len(meetings),
            "meetings":  meetings
        }
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Intelligence ───────────────────────────────────────

@app.get("/clients/{client_id}/score", tags=["Intelligence"])
async def score_client_endpoint(
    client_id: str,
    username:  str = Depends(verify_credentials)
):
    """AI scores a client on multiple dimensions"""
    try:
        client = await sheets.require_client(client_id)
        score  = await score_single_client(client)
        asyncio.create_task(sheets.log_activity(
            client_id, "CLIENT_SCORED",
            f"Score: {score.get('lead_score')}/10 | "
            f"Churn: {score.get('churn_risk')} | "
            f"Close: {score.get('estimated_close_probability')}%",
            "SUCCESS", ""
        ))
        return {
            "ok":          True,
            "client_id":   client_id,
            "client_name": client.get("name"),
            "score":       score
        }
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        logger.error(f"Scoring failed: {e}")
        raise HTTPException(500, str(e))


@app.get("/pipeline/score", tags=["Intelligence"])
async def score_pipeline_endpoint(
    username: str = Depends(verify_credentials)
):
    """AI analyzes entire pipeline health"""
    try:
        clients = await sheets.get_all_clients(limit=1000)
        if not clients:
            raise HTTPException(400, "No clients in pipeline")
        analysis = await score_entire_pipeline(clients)
        return {
            "ok":                      True,
            "total_clients_analyzed":  len(clients),
            "analysis":                analysis
        }
    except Exception as e:
        logger.error(f"Pipeline scoring failed: {e}")
        raise HTTPException(500, str(e))


@app.get("/clients/{client_id}/similar", tags=["Intelligence"])
async def find_similar_clients_endpoint(
    client_id: str,
    username:  str = Depends(verify_credentials)
):
    """Find clients similar to a target"""
    try:
        target      = await sheets.require_client(client_id)
        all_clients = await sheets.get_all_clients(limit=1000)
        result      = await find_similar_clients(target, all_clients)
        return {
            "ok":          True,
            "client_id":   client_id,
            "client_name": target.get("name"),
            **result
        }
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/recommendations/daily", tags=["Intelligence"])
async def daily_recommendations(
    username: str = Depends(verify_credentials)
):
    """AI recommends who to follow up with today"""
    try:
        clients = await sheets.get_all_clients(limit=1000)
        if not clients:
            raise HTTPException(400, "No clients found")
        recommendations = await get_daily_recommendations(clients)
        return {
            "ok":              True,
            "total_clients":   len(clients),
            "recommendations": recommendations
        }
    except Exception as e:
        logger.error(f"Daily recommendations failed: {e}")
        raise HTTPException(500, str(e))


@app.get("/recommendations/stale", tags=["Intelligence"])
async def stale_clients(
    days_inactive: int = Query(14, ge=1, le=365),
    username:      str = Depends(verify_credentials)
):
    """Find clients with no activity for X days"""
    try:
        from datetime import datetime, timedelta
        all_activities = await sheets.search_activities(limit=1000)
        cutoff = (
            datetime.utcnow() - timedelta(days=days_inactive)
        ).isoformat()
        active_ids = {
            a["client_id"]
            for a in all_activities
            if a.get("timestamp", "") >= cutoff
        }
        all_clients = await sheets.get_all_clients(limit=1000)
        stale = [
            c for c in all_clients
            if c["client_id"] not in active_ids
            and c.get("stage") not in ("Won", "Lost")
        ]
        return {
            "ok":            True,
            "days_inactive": days_inactive,
            "stale_count":   len(stale),
            "stale_clients": stale
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/insights/patterns", tags=["Intelligence"])
async def pipeline_pattern_detection(
    username: str = Depends(verify_credentials)
):
    """AI detects patterns across the pipeline"""
    try:
        clients = await sheets.get_all_clients(limit=1000)
        if not clients:
            raise HTTPException(400, "No clients to analyze")
        patterns = await pipeline_patterns(clients)
        return {
            "ok":                     True,
            "total_clients_analyzed": len(clients),
            "patterns":               patterns
        }
    except Exception as e:
        logger.error(f"Pattern detection failed: {e}")
        raise HTTPException(500, str(e))


@app.get("/insights/revenue-forecast", tags=["Intelligence"])
async def revenue_forecast_endpoint(
    username: str = Depends(verify_credentials)
):
    """AI forecasts pipeline revenue"""
    try:
        clients = await sheets.get_all_clients(limit=1000)
        if not clients:
            raise HTTPException(400, "No clients to forecast")
        forecast = await forecast_revenue(clients)
        return {
            "ok":            True,
            "total_clients": len(clients),
            "forecast":      forecast
        }
    except Exception as e:
        logger.error(f"Forecast failed: {e}")
        raise HTTPException(500, str(e))


@app.get("/insights/win-loss", tags=["Intelligence"])
async def win_loss_analysis_endpoint(
    username: str = Depends(verify_credentials)
):
    """AI analyzes won and lost deals"""
    try:
        clients = await sheets.get_all_clients(limit=1000)
        won  = [c for c in clients if c.get("stage") == "Won"]
        lost = [c for c in clients if c.get("stage") == "Lost"]
        if not won and not lost:
            raise HTTPException(
                400, "No won or lost deals to analyze yet"
            )
        analysis = await analyze_win_loss(clients)
        return {
            "ok":        True,
            "won_count":  len(won),
            "lost_count": len(lost),
            "analysis":   analysis
        }
    except Exception as e:
        logger.error(f"Win/loss analysis failed: {e}")
        raise HTTPException(500, str(e))


# ── Search ─────────────────────────────────────────────

@app.post("/search", tags=["Search"])
async def natural_language_search_endpoint(
    data:     NLSearchInput,
    username: str = Depends(verify_credentials)
):
    """Search clients using natural language"""
    try:
        clients = await sheets.get_all_clients(limit=1000)
        if not clients:
            return {
                "ok":             True,
                "query":          data.query,
                "total_matches":  0,
                "matched_clients": []
            }
        result = await nl_search(data.query, clients)
        asyncio.create_task(sheets.log_agent(
            "NL_SEARCH", data.query,
            f"Found {result.get('total_matches', 0)} matches"
        ))
        return {"ok": True, "query": data.query, **result}
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(500, str(e))


@app.post("/search/filter", tags=["Search"])
async def smart_filter_endpoint(
    data:     SmartFilterInput,
    username: str = Depends(verify_credentials)
):
    """Filter clients with natural language criteria"""
    try:
        clients = await sheets.get_all_clients(limit=1000)
        result  = await smart_filter(data.criteria, clients)
        asyncio.create_task(sheets.log_agent(
            "SMART_FILTER", data.criteria,
            f"Found {result.get('total_matches', 0)} matches"
        ))
        return {"ok": True, "criteria": data.criteria, **result}
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Documents: Contracts / Invoices / Proposals ────────

@app.post("/clients/{client_id}/contract", tags=["Documents"])
async def create_contract(
    client_id: str,
    data:      GenerateContractInput,
    username:  str = Depends(verify_credentials)
):
    """Generate a professional service contract"""
    try:
        import uuid
        client        = await sheets.require_client(client_id)
        contract_data = data.model_dump()
        contract_data["contract_number"] = (
            "CON-" + str(uuid.uuid4())[:8].upper()
        )
        contract_bytes = generate_contract(client, contract_data)
        asyncio.create_task(sheets.log_activity(
            client_id, "CONTRACT_GENERATED",
            f"Contract for {client['name']}", "SUCCESS", ""
        ))
        return Response(
            content=contract_bytes,
            media_type=(
                "application/vnd.openxmlformats-officedocument"
                ".wordprocessingml.document"
            ),
            headers={
                "Content-Disposition":
                    f"attachment; filename=contract_{client_id}.docx"
            }
        )
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/clients/{client_id}/invoice", tags=["Documents"])
async def create_invoice(
    client_id: str,
    data:      GenerateInvoiceInput,
    username:  str = Depends(verify_credentials)
):
    """Generate a professional invoice"""
    try:
        client       = await sheets.require_client(client_id)
        invoice_data = data.model_dump()
        invoice_data["line_items"] = [
            item if isinstance(item, dict) else item.model_dump()
            for item in data.line_items
        ]
        invoice_bytes = generate_invoice(client, invoice_data)
        asyncio.create_task(sheets.log_activity(
            client_id, "INVOICE_GENERATED",
            f"Invoice for {client['name']}", "SUCCESS", ""
        ))
        return Response(
            content=invoice_bytes,
            media_type=(
                "application/vnd.openxmlformats-officedocument"
                ".wordprocessingml.document"
            ),
            headers={
                "Content-Disposition":
                    f"attachment; filename=invoice_{client_id}.docx"
            }
        )
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/clients/{client_id}/proposal", tags=["Documents"])
async def create_proposal(
    client_id: str,
    data:      GenerateProposalInput,
    username:  str = Depends(verify_credentials)
):
    """Generate a professional proposal"""
    try:
        client         = await sheets.require_client(client_id)
        proposal_bytes = generate_proposal(client, data.model_dump())
        asyncio.create_task(sheets.log_activity(
            client_id, "PROPOSAL_GENERATED",
            f"Proposal for {client['name']}", "SUCCESS", ""
        ))
        asyncio.create_task(sheets.update_stage(
            client_id, "Proposal Sent", changed_by=username
        ))
        return Response(
            content=proposal_bytes,
            media_type=(
                "application/vnd.openxmlformats-officedocument"
                ".wordprocessingml.document"
            ),
            headers={
                "Content-Disposition":
                    f"attachment; filename=proposal_{client_id}.docx"
            }
        )
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/clients/{client_id}/ai-proposal", tags=["Documents"])
async def ai_generate_proposal(
    client_id:      str,
    provider_name:  str           = Query(...),
    provider_email: Optional[str] = Query(None),
    username:       str           = Depends(verify_credentials)
):
    """AI automatically generates a complete proposal"""
    try:
        client   = await sheets.require_client(client_id)
        analysis = await analyze_client(client)
        proposal_data = {
            "provider_name":     provider_name,
            "provider_email":    provider_email,
            "executive_summary": analysis.get(
                "executive_summary", ""
            ),
            "problem_statement": analysis.get(
                "business_problem", ""
            ),
            "proposed_solution": (
                f"We propose to address your "
                f"{client.get('service', 'needs')} "
                f"through our proven methodology."
            ),
            "scope_items":  analysis.get("recommendations", []),
            "next_steps":   [
                "Review proposal",
                "Discovery call",
                "Sign agreement",
                "Project kickoff"
            ],
            "why_us": [
                "Proven track record",
                "Dedicated support",
                "Transparent pricing",
                "On-time delivery"
            ]
        }
        proposal_bytes = generate_proposal(client, proposal_data)
        asyncio.create_task(sheets.log_activity(
            client_id, "AI_PROPOSAL_GENERATED",
            f"AI proposal for {client['name']}", "SUCCESS", ""
        ))
        return Response(
            content=proposal_bytes,
            media_type=(
                "application/vnd.openxmlformats-officedocument"
                ".wordprocessingml.document"
            ),
            headers={
                "Content-Disposition":
                    f"attachment; filename=ai_proposal_{client_id}.docx"
            }
        )
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Reports ────────────────────────────────────────────

@app.get("/reports/weekly", tags=["Reports"])
async def weekly_report(
    username: str = Depends(verify_credentials)
):
    """Download weekly performance report"""
    try:
        clients      = await sheets.get_all_clients(limit=1000)
        activities   = await sheets.search_activities(limit=500)
        pipeline     = await sheets.get_pipeline_summary()
        report_bytes = generate_weekly_report(
            clients, activities, pipeline
        )
        return Response(
            content=report_bytes,
            media_type=(
                "application/vnd.openxmlformats-officedocument"
                ".wordprocessingml.document"
            ),
            headers={
                "Content-Disposition":
                    "attachment; filename=weekly_report.docx"
            }
        )
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/reports/monthly", tags=["Reports"])
async def monthly_report(
    month:    Optional[str] = Query(None),
    username: str           = Depends(verify_credentials)
):
    """Download monthly pipeline report"""
    try:
        clients      = await sheets.get_all_clients(limit=1000)
        activities   = await sheets.search_activities(limit=1000)
        pipeline     = await sheets.get_pipeline_summary()
        report_bytes = generate_monthly_report(
            clients, activities, pipeline, month
        )
        return Response(
            content=report_bytes,
            media_type=(
                "application/vnd.openxmlformats-officedocument"
                ".wordprocessingml.document"
            ),
            headers={
                "Content-Disposition":
                    "attachment; filename=monthly_report.docx"
            }
        )
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/reports/acquisition", tags=["Reports"])
async def acquisition_report(
    username: str = Depends(verify_credentials)
):
    """Download client acquisition report"""
    try:
        clients      = await sheets.get_all_clients(limit=1000)
        report_bytes = generate_client_acquisition_report(clients)
        return Response(
            content=report_bytes,
            media_type=(
                "application/vnd.openxmlformats-officedocument"
                ".wordprocessingml.document"
            ),
            headers={
                "Content-Disposition":
                    "attachment; filename=acquisition_report.docx"
            }
        )
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/reports/agent-activity", tags=["Reports"])
async def agent_activity_report(
    username: str = Depends(verify_credentials)
):
    """Download agent activity report"""
    try:
        activities   = await sheets.search_activities(limit=1000)
        spreadsheet  = sheets.get_spreadsheet()

        def _get_logs():
            ws = spreadsheet.worksheet("Agent Logs")
            return ws.get_all_records()

        agent_logs   = await asyncio.to_thread(_get_logs)
        report_bytes = generate_agent_activity_report(
            activities, agent_logs
        )
        return Response(
            content=report_bytes,
            media_type=(
                "application/vnd.openxmlformats-officedocument"
                ".wordprocessingml.document"
            ),
            headers={
                "Content-Disposition":
                    "attachment; filename=agent_activity_report.docx"
            }
        )
    except Exception as e:
        raise HTTPException(500, str(e))


# ── ARIA Chat File Upload ──────────────────────────────

@app.post("/aria/chat/upload", tags=["ARIA"])
async def aria_chat_upload(
    file:            UploadFile = File(...),
    message:         str        = Form(default=""),
    history:         str        = Form(default="[]"),
    session_context: str        = Form(default="{}"),
    username:        str        = Depends(verify_credentials)
):
    """
    ARIA chat with file attachment.
    Supports: PDF (analyze), Excel/CSV (import or analyze),
    Word (read and answer questions).
    """
    try:
        from app.services.importer import process_chat_file

        file_bytes = await file.read()
        filename   = file.filename or "uploaded_file"

        # Parse history and context from form
        try:
            history_list = json.loads(history)
        except Exception:
            history_list = []

        try:
            ctx = json.loads(session_context)
        except Exception:
            ctx = {}

        # Rebuild AgentChat history objects
        from app.models import HistoryMessage
        history_msgs = [
            HistoryMessage(
                role=m.get("role", "user"),
                content=m.get("content", "")
            )
            for m in history_list
            if isinstance(m, dict)
        ]

        # Process the file
        file_result = await process_chat_file(
            filename, file_bytes, message
        )

        file_type = file_result.get("file_type", "unknown")
        action    = file_result.get("action", "unknown")
        summary   = file_result.get("summary", "")

        settings = get_settings()
        pipeline = await sheets.get_pipeline_summary()

        # ── Import path ────────────────────────────────
        if action == "import" and file_result.get("rows"):
            rows = file_result["rows"]

            if len(rows) == 0:
                reply = (
                    f"I found the file **{filename}** but "
                    f"there were no valid rows to import. "
                    f"Please check the format guide on the "
                    f"Import page."
                )
            else:
                # Run bulk import
                from app.services.importer import \
                    bulk_import_clients
                result = await bulk_import_clients(
                    rows, sheets, check_duplicates=True
                )

                imported = result.get("imported", 0)
                skipped  = result.get("skipped", 0)
                failed   = result.get("failed", 0)

                names = ", ".join(
                    c.get("name", "")
                    for c in (
                        result.get("imported_clients", [])[:5]
                    )
                )
                more = (
                    f" and {imported - 5} more"
                    if imported > 5 else ""
                )

                reply = (
                    f"✅ Imported **{imported}** client"
                    f"{'s' if imported != 1 else ''} "
                    f"from **{filename}**!\n\n"
                    + (f"Imported: {names}{more}\n" if names else "")
                    + (f"Skipped (duplicates): {skipped}\n" if skipped else "")
                    + (f"Failed: {failed}\n" if failed else "")
                    + f"\nAll clients are now in Google Sheets. "
                    f"Go to the Clients page to view them."
                )

            asyncio.create_task(sheets.log_agent(
                "ARIA_FILE_IMPORT",
                filename,
                f"Imported via chat: {summary}"
            ))

        # ── Analyze path ───────────────────────────────
        elif action == "analyze":
            doc_text = file_result.get("text", "")

            if not doc_text.strip():
                reply = (
                    f"I opened **{filename}** but couldn't "
                    f"extract any readable text. The file may "
                    f"be image-based or corrupted."
                )
            else:
                user_q = message.strip() or (
                    f"What is in this {file_type.upper()} file? "
                    f"Summarize key information and any "
                    f"client-related details."
                )

                reply = await analyze_document_content(
                    doc_text, user_q, file_type
                )

                asyncio.create_task(sheets.log_agent(
                    "ARIA_FILE_ANALYZE",
                    filename,
                    f"Analyzed {file_type}: {summary}"
                ))

        else:
            reply = (
                f"I received **{filename}** but it's a "
                f"file type I can't process yet. "
                f"Supported: PDF, Excel (.xlsx/.xls), "
                f"CSV, Word (.docx)."
            )

        return {
            "ok":              True,
            "response":        reply,
            "action_executed": f"Processed {filename}",
            "needs_confirmation": False,
            "context": {
                "lastAction":    f"uploaded {filename}",
                "pendingAction": None
            },
            "file_info": {
                "filename":  filename,
                "file_type": file_type,
                "action":    action,
                "summary":   summary
            }
        }

    except Exception as e:
        logger.error(f"ARIA file upload failed: {e}")
        return {
            "ok":       False,
            "response": (
                f"Sorry, I had trouble processing "
                f"**{file.filename}**: {str(e)}\n\n"
                f"Please try again or use the Bulk "
                f"Import page for Excel/CSV files."
            ),
            "action_executed":    None,
            "needs_confirmation": False,
            "context":            {}
        }


# ── ARIA Chat ──────────────────────────────────────────

async def execute_aria_action(
    action: dict,
    settings,
    sheets_module
) -> tuple:
    """
    Execute a CRM action from ARIA chat.
    Returns (summary_string, result_dict).
    """
    action_type = action.get("action_type", "none")
    client_id   = action.get("client_id")
    summary     = ""
    result      = {}

    try:
        if action_type == "create_client":
            data = {
                "name":     action.get("name", ""),
                "email":    action.get("email"),
                "company":  action.get("company"),
                "phone":    action.get("phone"),
                "service":  action.get("service"),
                "priority": action.get("priority", "Medium"),
                "stage":    action.get("stage", "New"),
                "notes":    action.get("notes")
            }
            client  = await sheets_module.create_client(data)
            summary = (
                f"✅ Created: {client['name']} "
                f"| ID: {client['client_id']} "
                f"| Saved to Google Sheets"
            )
            result = client

        elif action_type == "update_stage" and client_id:
            res     = await sheets_module.update_stage(
                client_id,
                action.get("new_stage", "New"),
                changed_by="aria"
            )
            summary = (
                f"✅ Stage: {res.get('previous_stage')} → "
                f"{res.get('new_stage')} | Google Sheets updated"
            )
            result = res

        elif action_type == "update_client" and client_id:
            updates = action.get("update_fields", {})
            if updates:
                res     = await sheets_module.update_client(
                    client_id, updates, changed_by="aria"
                )
                summary = (
                    f"✅ Updated {list(updates.keys())} "
                    f"| Google Sheets updated"
                )
                result = res or {}

        elif action_type in ("send_email", "create_draft"):
            to = action.get("recipient_email")
            if client_id and not to:
                client = await sheets_module.require_client(
                    client_id
                )
                to = client.get("email")
            if not to:
                summary = "❌ No recipient email found"
            else:
                if action.get("update_email_in_crm") and client_id:
                    await sheets_module.update_client(
                        client_id, {"email": to}, changed_by="aria"
                    )

                if action_type == "send_email":
                    from app.services.gmail import (
                        send_email as gs
                    )
                    res     = await gs(
                        to=to,
                        subject=action.get("subject", "Follow up"),
                        body=action.get("body", ""),
                        from_email=settings.gmail_address
                    )
                    if client_id:
                        asyncio.create_task(
                            sheets_module.log_activity(
                                client_id, "EMAIL_SENT",
                                f"ARIA sent to {to}",
                                "SUCCESS", ""
                            )
                        )
                    summary = (
                        f"✅ Email sent to {to} "
                        f"| Message ID: {res.get('message_id', '')}"
                    )
                    result = res
                else:
                    from app.services.gmail import (
                        create_draft as gd
                    )
                    res     = await gd(
                        to=to,
                        subject=action.get("subject", "Follow up"),
                        body=action.get("body", ""),
                        from_email=settings.gmail_address
                    )
                    if client_id:
                        asyncio.create_task(
                            sheets_module.log_activity(
                                client_id, "EMAIL_DRAFT",
                                f"ARIA draft for {to}",
                                "SUCCESS",
                                res.get("gmail_drafts_url", "")
                            )
                        )
                    summary = (
                        f"✅ Draft saved to Gmail for {to} "
                        f"| Draft ID: {res.get('draft_id', '')}"
                    )
                    result = res

        elif action_type == "schedule_meeting" and client_id:
            from app.services.calendar import (
                schedule_meeting as sm
            )
            from datetime import datetime, timedelta

            def parse_dt(s):
                if not s:
                    return None
                s = str(s).strip()
                for fmt in [
                    "%Y-%m-%dT%H:%M:%S",
                    "%Y-%m-%dT%H:%M",
                    "%Y-%m-%d %H:%M:%S",
                    "%Y-%m-%d %H:%M",
                    "%Y-%m-%d"
                ]:
                    try:
                        return datetime.strptime(
                            s[:19], fmt
                        ).strftime("%Y-%m-%dT%H:%M:%S-06:00")
                    except Exception:
                        continue
                return s

            ps = parse_dt(action.get("start_time", ""))
            pe = parse_dt(action.get("end_time", ""))

            if ps and not pe:
                try:
                    pe = (
                        datetime.fromisoformat(
                            ps.replace("Z", "+00:00")
                        ) + timedelta(hours=1)
                    ).strftime("%Y-%m-%dT%H:%M:%S-06:00")
                except Exception:
                    pe = ps

            if not ps:
                summary = "❌ Could not parse meeting time"
            else:
                client  = await sheets_module.require_client(client_id)
                res     = await sm(
                    client=client,
                    title=action.get(
                        "title",
                        f"Meeting — {client.get('name')}"
                    ),
                    start_time=ps,
                    end_time=pe,
                    description=action.get("description", ""),
                    location=action.get("location", ""),
                    invite_client=action.get(
                        "invite_client", False
                    )
                )
                asyncio.create_task(
                    sheets_module.log_activity(
                        client_id, "MEETING_SCHEDULED",
                        f"ARIA: {res.get('title')}",
                        "SUCCESS", res.get("calendar_link", "")
                    )
                )
                summary = (
                    f"✅ Meeting: {res.get('title')} "
                    f"| {res.get('start_time')} "
                    f"| Google Calendar updated"
                )
                result = res

        elif action_type == "score_client" and client_id:
            client  = await sheets_module.require_client(client_id)
            score   = await score_single_client(client)
            summary = (
                f"✅ Score: {score.get('lead_score')}/10 "
                f"| Churn: {score.get('churn_risk')} "
                f"| Close: {score.get('estimated_close_probability')}%"
            )
            result = score

        elif action_type == "delete_client" and client_id:
            res     = await sheets_module.delete_client_permanently(
                client_id
            )
            summary = (
                f"✅ Permanently deleted {res.get('name')} "
                f"| Say 'undo delete' to restore within 1 hour"
            )
            result = res

        elif action_type == "archive_client" and client_id:
            res     = await sheets_module.archive_client(client_id)
            summary = f"✅ Client archived | Google Sheets updated"
            result  = res

        elif action_type == "restore_deleted":
            from app.services.sheets import (
                restore_deleted_client as rdc
            )
            id_to_restore = action.get("client_id")
            res           = await rdc(id_to_restore)
            summary       = (
                f"✅ Restored deleted client: {res.get('name')} "
                f"| Back in Google Sheets"
            )
            result = res

        elif action_type == "rollback_last" and client_id:
            res     = await sheets_module.rollback_last_change(
                client_id
            )
            summary = (
                f"✅ Rolled back '{res.get('field')}': "
                f"'{res.get('rolled_back_from')}' → "
                f"'{res.get('rolled_back_to')}'"
            )
            result = res

        elif action_type == "rollback_field" and client_id:
            field = action.get("field")
            if field:
                res     = await sheets_module.rollback_client_field(
                    client_id, field
                )
                summary = (
                    f"✅ Rolled back '{field}': "
                    f"'{res.get('rolled_back_from')}' → "
                    f"'{res.get('rolled_back_to')}'"
                )
                result = res

        elif action_type == "update_followup" and client_id:
            date = action.get("follow_up_date")
            if date:
                res     = await sheets_module.update_next_followup(
                    client_id, date
                )
                summary = (
                    f"✅ Follow-up set to {date} "
                    f"| Google Sheets updated"
                )
                result = res

    except Exception as e:
        logger.error(f"Action failed [{action_type}]: {e}")
        summary = f"❌ Failed: {str(e)}"

    return summary, result


@app.post("/aria/chat", tags=["ARIA"])
async def aria_chat(
    data:     AgentChat,
    username: str = Depends(verify_credentials)
):
    """ARIA — AI CRM assistant with full action execution"""
    try:
        settings = get_settings()

        # Load CRM context
        pipeline    = await sheets.get_pipeline_summary()
        all_clients = await sheets.get_all_clients(limit=100)

        client_list = [
            {
                "client_id":    c.get("client_id"),
                "name":         c.get("name"),
                "company":      c.get("company"),
                "stage":        c.get("stage"),
                "priority":     c.get("priority"),
                "email":        c.get("email"),
                "phone":        c.get("phone"),
                "service":      c.get("service"),
                "next_follow_up": c.get("next_follow_up"),
                "notes":        str(c.get("notes", ""))[:150]
            }
            for c in all_clients
        ]

        # Build conversation history text
        history_text = ""
        if data.history:
            history_text = (
                "\nCONVERSATION HISTORY:\n"
                + "=" * 40 + "\n"
            )
            for msg in data.history[-10:]:  # Last 10 msgs
                role = "User" if msg.role == "user" else "ARIA"
                history_text += f"{role}: {msg.content}\n"
            history_text += "=" * 40 + "\n"

        # Session context
        ctx          = data.session_context or {}
        session_text = ""
        if ctx.get("lastClientName"):
            session_text += (
                f"\nLast discussed: {ctx['lastClientName']} "
                f"({ctx.get('lastClientId')})\n"
            )
        if ctx.get("pendingAction"):
            session_text += (
                f"Pending: "
                f"{json.dumps(ctx['pendingAction'])}\n"
            )
        if ctx.get("lastCompletedAction"):
            session_text += (
                f"Last done: "
                f"{ctx['lastCompletedAction']}\n"
            )
            
        # ── Topic Firewall ─────────────────────────────
        msg_lower_fw = data.message.lower().strip()

        # Only auto-pass messages that are clearly
        # short follow-ups or explicit CRM keywords.
        # Never auto-pass just because history exists —
        # that's what allowed the Python question through.
        _CONFIRM_WORDS = {
            "yes", "no", "ok", "okay", "sure", "yep", "yup",
            "go ahead", "do it", "confirm", "cancel", "stop",
            "undo", "rollback", "revert", "restore", "proceed",
            "yes go ahead", "never mind", "nevermind"
        }

        _CRM_KEYWORDS = {
            "client", "lead", "contact", "prospect", "deal",
            "pipeline", "stage", "follow up", "followup",
            "email", "draft", "send mail", "send email",
            "meeting", "schedule", "calendar", "appointment",
            "report", "invoice", "contract", "proposal",
            "score", "import", "export", "upload", "csv",
            "excel", "delete", "archive", "restore", "create",
            "update", "add client", "new client", "show me",
            "list", "who", "which clients", "high priority",
            "won", "lost", "revenue", "forecast", "analyze",
            "analysis", "rollback", "undo delete", "generate"
        }

        _auto_pass = (
            # Exact confirmation / cancellation words
            msg_lower_fw in _CONFIRM_WORDS
            # Pending action — must let confirmation through
            or bool(ctx.get("pendingAction"))
            # Contains explicit CRM keyword
            or any(kw in msg_lower_fw for kw in _CRM_KEYWORDS)
        )

        if not _auto_pass:
            _guard_prompt = (
                f"You are a strict topic classifier for a "
                f"CRM business assistant.\n"
                f"Is this message related to CRM, sales, "
                f"clients, pipeline, email, meetings, or "
                f"business operations?\n\n"
                f"Message: \"{data.message}\"\n\n"
                f"Blocked examples:\n"
                f"- 'give python code to reverse a string'\n"
                f"- 'write me a poem'\n"
                f"- 'what is the capital of France'\n"
                f"- 'explain quantum physics'\n\n"
                f"Allowed examples:\n"
                f"- 'give me a pipeline summary'\n"
                f"- 'analyze it' (follow-up to CRM question)\n"
                f"- 'generate it' (follow-up to CRM question)\n"
                f"- 'send an email to Sarah'\n"
                f"- 'who needs follow up today'\n\n"
                f"Respond with ONLY one word: ALLOWED or BLOCKED"
            )

            _guard = await generate(
                _guard_prompt, expect_json=False
            )

            if "BLOCKED" in _guard.strip().upper():
                return {
                    "ok":                 True,
                    "response":           (
                        "I'm ARIA, your CRM assistant — I can only "
                        "help with clients, pipeline, emails, "
                        "meetings, reports, and sales.\n\n"
                        "What would you like to do?"
                    ),
                    "action_executed":    None,
                    "needs_confirmation": False,
                    "context":            {}
                }
        # ── End Firewall ────────────────────────────────

        # ── Intent Detection ───────────────────────────
        intent_prompt = f"""You are ARIA, an AI CRM assistant.
Determine the user's intent and extract action parameters.

{history_text}
SESSION: {session_text}

CURRENT MESSAGE: {data.message}

CLIENTS (first 50):
{json.dumps(client_list[:50], indent=2)}

PIPELINE:
Total: {pipeline.get('total_clients', 0)}
High Priority: {pipeline.get('high_priority_pending_count', 0)}
Won: {pipeline.get('won_count', 0)}
Stages: {json.dumps(pipeline.get('stage_counts', {}))}

RULES:
1. Use full history to resolve pronouns (he/she/they/it → client)
2. "yes/confirm/go ahead/sure/ok" → is_confirmation=true
3. "no/cancel/stop" → is_cancellation=true
4. "undo/rollback/revert" → action_type=rollback_last
5. "undo delete/restore deleted" → action_type=restore_deleted
6. Match client by name from the clients list
7. Use email from user message if provided
8. Convert times to ISO: 2026-06-20T14:00:00-06:00
9. score_client / rollback_last / rollback_field → needs_confirmation=false
10. Everything else → needs_confirmation=true
11. For emails without address → use client's email from CRM

RESPOND WITH ONLY VALID JSON:
{{
  "is_action": true,
  "is_confirmation": false,
  "is_cancellation": false,
  "needs_confirmation": true,
  "action_type": "create_client|update_stage|update_client|send_email|create_draft|schedule_meeting|score_client|archive_client|delete_client|restore_deleted|rollback_last|rollback_field|update_followup|none",
  "client_id": "CL-XXXXXXXX or null",
  "client_name": "matched client name or null",
  "name": "for create_client",
  "email": "email address",
  "company": "company name",
  "phone": "phone number",
  "service": "service type",
  "priority": "High|Medium|Low",
  "stage": "New|Contacted|Consultation Scheduled|Proposal Sent|Won|Lost",
  "notes": "notes text",
  "new_stage": "for update_stage",
  "update_fields": {{}},
  "recipient_email": "for emails",
  "update_email_in_crm": false,
  "subject": "email subject",
  "body": "full email body",
  "title": "meeting title",
  "start_time": "ISO datetime",
  "end_time": "ISO datetime or null",
  "location": "location",
  "description": "meeting description",
  "invite_client": false,
  "field": "for rollback_field",
  "follow_up_date": "YYYY-MM-DD",
  "confirmation_summary": "one line of exactly what will happen"
}}"""

        intent_text = await generate(
            intent_prompt, expect_json=True
        )

        try:
            intent = json.loads(intent_text)
        except json.JSONDecodeError:
            match  = re.search(r'\{.*\}', intent_text, re.DOTALL)
            intent = (
                json.loads(match.group())
                if match else {"is_action": False}
            )

        # ── Execute Action ─────────────────────────────
        action_summary = ""
        action_result  = {}
        pending_action = None
        executed       = False

        is_confirmation = intent.get("is_confirmation", False)
        is_cancellation = intent.get("is_cancellation", False)
        is_action       = intent.get("is_action", False)
        needs_confirm   = intent.get("needs_confirmation", True)
        action_type     = intent.get("action_type", "none")

        # These never need confirmation
        read_only = {
            "score_client",
            "rollback_last",
            "rollback_field"
        }

        if is_cancellation:
            action_summary = "cancelled"

        elif is_confirmation and ctx.get("pendingAction"):
            action_summary, action_result = \
                await execute_aria_action(
                    ctx["pendingAction"], settings, sheets
                )
            executed = True

        elif is_action and action_type in read_only:
            action_summary, action_result = \
                await execute_aria_action(
                    intent, settings, sheets
                )
            executed = True

        elif (
            is_action and
            action_type != "none" and
            needs_confirm
        ):
            pending_action = intent

        elif (
            is_action and
            action_type != "none" and
            not needs_confirm
        ):
            action_summary, action_result = \
                await execute_aria_action(
                    intent, settings, sheets
                )
            executed = True

        # ── Generate Reply ─────────────────────────────
        if action_summary == "cancelled":
            instruction = (
                "User cancelled. Acknowledge warmly, offer help."
            )
        elif pending_action:
            instruction = (
                f"About to do: "
                f"{intent.get('confirmation_summary', 'this action')}\n"
                f"Details: {json.dumps(pending_action, indent=2)}\n"
                f"Describe exactly what will happen. "
                f"End with 'Shall I go ahead?'"
            )
        elif executed and action_summary:
            instruction = (
                f"Just completed: {action_summary}\n"
                f"Tell user what was done. Be specific about "
                f"Google Sheets/Gmail/Calendar. "
                f"Mention they can say 'undo' to reverse. "
                f"Suggest a relevant next step."
            )
        else:
            instruction = (
                "Answer the user using CRM data. "
                "Be specific, helpful, and concise.\n\n"
                "If they mention bulk import, multiple clients, "
                "Excel/CSV upload — direct them to /aria/import. "
                "They can drag and drop the file for live import.\n\n"
                "If they just uploaded a file — tell them what "
                "you found and what action was taken."
            )

        response_prompt = (
            f"You are ARIA, AI Relationship Intelligence.\n"
            f"{history_text}\n"
            f"SESSION: {session_text}\n\n"
            f"CRM: {pipeline.get('total_clients', 0)} clients | "
            f"High: {pipeline.get('high_priority_pending_count', 0)} | "
            f"Won: {pipeline.get('won_count', 0)}\n\n"
            f"USER: {data.message}\n\n"
            f"TASK: {instruction}\n\n"
            f"Rules:\n"
            f"- Reference history for context\n"
            f"- Use client names, not just IDs\n"
            f"- Warm, professional, concise\n"
            f"- No markdown headers\n\n"
            f"ARIA:"
        )

        reply = await generate(response_prompt)

        # ── Update Session Context ─────────────────────
        context_update = {}
        msg_lower      = data.message.lower()

        # Find mentioned client
        mentioned = next(
            (
                c for c in all_clients
                if c.get("name", "").lower() in msg_lower
                or c.get("client_id", "").lower() in msg_lower
            ),
            None
        )

        # Fall back to last discussed client
        if not mentioned and ctx.get("lastClientId"):
            mentioned = next(
                (
                    c for c in all_clients
                    if c.get("client_id") ==
                    ctx["lastClientId"]
                ),
                None
            )

        if (
            executed and
            action_type == "create_client" and
            action_result.get("client_id")
        ):
            context_update["lastClientId"] = \
                action_result["client_id"]
            context_update["lastClientName"] = \
                action_result.get("name", "")
        elif mentioned:
            context_update["lastClientId"] = \
                mentioned.get("client_id")
            context_update["lastClientName"] = \
                mentioned.get("name")

        context_update["lastAction"] = data.message

        if pending_action:
            context_update["pendingAction"] = pending_action
        elif executed:
            context_update["pendingAction"] = None
            context_update["lastCompletedAction"] = {
                "summary":     action_summary,
                "action_type": action_type,
                "client_id":   intent.get("client_id")
            }
        elif action_summary == "cancelled":
            context_update["pendingAction"] = None

        asyncio.create_task(
            sheets.log_agent("ARIA_CHAT", data.message, reply)
        )

        return {
            "ok":               True,
            "message":          data.message,
            "response":         reply,
            "action_executed":  (
                action_summary
                if executed and action_summary and
                action_summary != "cancelled"
                else None
            ),
            "needs_confirmation": bool(pending_action),
            "context":          context_update
        }

    except Exception as e:
        msg = str(e)
        logger.error(f"ARIA chat failed: {e}")
        if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
            raise HTTPException(
                429,
                "Rate limit reached. Please wait 30 seconds."
            )
        raise HTTPException(500, msg)