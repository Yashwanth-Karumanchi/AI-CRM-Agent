from fastapi import (
    FastAPI, Depends, UploadFile,
    File, HTTPException, Query
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
from app.models import (
    ScheduleMeetingInput,
    UpdateMeetingInput,
    MeetingNotesInput
)
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
import json

from app.auth import verify_credentials
from app.models import (
    ClientCreate, ClientUpdate, StageUpdate,
    EmailDraft, EmailSend, AgentChat,
    AgentDraftEmail, BulkStageUpdate,
    BulkArchive, FollowUpUpdate, DeleteDraftInput
)
from app.config import get_settings
from app.logger import get_logger
from app.services import sheets
from app.services.document import (
    generate_client_report,
    generate_pipeline_report
)
from app.services.pdf import extract_pdf_text
from app.services.gmail import (
    send_email, create_draft,
    delete_draft, list_drafts
)
from app.agent import (
    extract_client_from_pdf,
    analyze_client,
    draft_email,
    chat
)

from app.agent import (
    extract_client_from_pdf,
    analyze_client,
    draft_email,
    chat,
    score_single_client,
    score_entire_pipeline,
    find_similar_clients,
    get_daily_recommendations
)

from app.services.contracts import (
    generate_contract,
    generate_invoice,
    generate_proposal
)
from app.models import (
    GenerateContractInput,
    GenerateInvoiceInput,
    GenerateProposalInput,
    TimelineItem,
    LineItem,
    PricingTier
)

logger = get_logger(__name__)

app = FastAPI(
    title="AI CRM Agent",
    description="""
    Production-ready AI CRM Agent.

    ## Features
    - Full client CRUD with audit trail
    - Field-level rollback and undo
    - PDF extraction with AI
    - Word report generation
    - Gmail send and draft management
    - AI chat and client analysis
    - Pipeline management
    - Bulk operations
    - Follow-up tracking
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# ─── Startup ───────────────────────────────────────────

@app.on_event("startup")
async def startup():
    logger.info("Starting AI CRM Agent")
    try:
        sheets.setup_sheets()
        logger.info("Google Sheets initialized")
    except Exception as e:
        logger.error(f"Sheets setup failed: {e}")

# ─── System ────────────────────────────────────────────

@app.get("/health", tags=["System"])
async def health():
    return {
        "ok": True,
        "service": "AI CRM Agent",
        "version": "1.0.0"
    }

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

# ─── Clients: CRUD ─────────────────────────────────────

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
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/clients", tags=["Clients"])
async def list_clients(
    query: Optional[str] = Query(None),
    stage: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    client_id: Optional[str] = Query(None),
    email: Optional[str] = Query(None),
    include_archived: bool = Query(False),
    limit: int = Query(20, ge=1, le=100),
    username: str = Depends(verify_credentials)
):
    """Search and filter clients"""
    clients = await sheets.get_all_clients(
        query=query, stage=stage, priority=priority,
        client_id=client_id, email=email,
        include_archived=include_archived, limit=limit
    )
    return {"ok": True, "count": len(clients), "clients": clients}

@app.get("/clients/archived", tags=["Clients"])
async def get_archived_clients(
    username: str = Depends(verify_credentials)
):
    """Get all archived clients"""
    clients = await sheets.get_archived_clients()
    return {"ok": True, "count": len(clients), "clients": clients}

@app.get("/clients/{client_id}", tags=["Clients"])
async def get_client(
    client_id: str,
    username: str = Depends(verify_credentials)
):
    """Get a single client by ID"""
    try:
        client = await sheets.require_client(client_id)
        return {"ok": True, "client": client}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.put("/clients/{client_id}", tags=["Clients"])
async def update_client(
    client_id: str,
    data: ClientUpdate,
    username: str = Depends(verify_credentials)
):
    """Update client fields"""
    try:
        updates = data.model_dump(exclude_none=True)
        if not updates:
            raise HTTPException(400, "No fields to update")
        client = await sheets.update_client(
            client_id, updates, changed_by=username
        )
        return {"ok": True, "message": "Client updated", "client": client}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.put("/clients/{client_id}/stage", tags=["Clients"])
async def update_stage(
    client_id: str,
    data: StageUpdate,
    username: str = Depends(verify_credentials)
):
    """Update client pipeline stage"""
    try:
        result = await sheets.update_stage(
            client_id, data.stage.value, changed_by=username
        )
        return {"ok": True, "message": "Stage updated", **result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.put("/clients/{client_id}/followup", tags=["Clients"])
async def update_followup(
    client_id: str,
    data: FollowUpUpdate,
    username: str = Depends(verify_credentials)
):
    """Set next follow-up date"""
    try:
        result = await sheets.update_next_followup(
            client_id, data.follow_up_date
        )
        return {"ok": True, "message": "Follow-up updated", **result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.delete("/clients/{client_id}", tags=["Clients"])
async def archive_client(
    client_id: str,
    username: str = Depends(verify_credentials)
):
    """Soft delete - archive a client"""
    try:
        result = await sheets.archive_client(client_id)
        return {"ok": True, "message": "Client archived", **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/clients/{client_id}/restore", tags=["Clients"])
async def restore_client(
    client_id: str,
    username: str = Depends(verify_credentials)
):
    """Restore an archived client"""
    try:
        result = await sheets.restore_client(client_id)
        return {"ok": True, "message": "Client restored", **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/clients/{client_id}/permanent", tags=["Clients"])
async def delete_permanently(
    client_id: str,
    username: str = Depends(verify_credentials)
):
    """Permanently delete a client"""
    try:
        result = await sheets.delete_client_permanently(client_id)
        return {
            "ok": True,
            "message": "Client permanently deleted",
            **result
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

# ─── Clients: Bulk ─────────────────────────────────────

@app.post("/clients/bulk/stage", tags=["Bulk Operations"])
async def bulk_update_stage(
    data: BulkStageUpdate,
    username: str = Depends(verify_credentials)
):
    """Update stage for multiple clients"""
    result = await sheets.bulk_update_stage(
        data.client_ids, data.stage.value
    )
    return {"ok": True, **result}

@app.post("/clients/bulk/archive", tags=["Bulk Operations"])
async def bulk_archive(
    data: BulkArchive,
    username: str = Depends(verify_credentials)
):
    """Archive multiple clients"""
    result = await sheets.bulk_archive(data.client_ids)
    return {"ok": True, **result}

# ─── Audit & Rollback ──────────────────────────────────

@app.get("/clients/{client_id}/audit", tags=["Audit"])
async def get_audit_history(
    client_id: str,
    username: str = Depends(verify_credentials)
):
    """Get full audit trail for a client"""
    try:
        await sheets.require_client(client_id)
        history = await sheets.get_client_audit_history(client_id)
        return {
            "ok": True,
            "client_id": client_id,
            "count": len(history),
            "history": history
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/clients/{client_id}/rollback", tags=["Audit"])
async def rollback_last_change(
    client_id: str,
    username: str = Depends(verify_credentials)
):
    """Undo the last change made to a client"""
    try:
        result = await sheets.rollback_last_change(client_id)
        return {"ok": True, "message": "Last change rolled back", **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/clients/{client_id}/rollback/{field}", tags=["Audit"])
async def rollback_field(
    client_id: str,
    field: str,
    username: str = Depends(verify_credentials)
):
    """Rollback a specific field to its previous value"""
    try:
        result = await sheets.rollback_client_field(client_id, field)
        return {"ok": True, "message": f"Field '{field}' rolled back", **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# ─── Activity ──────────────────────────────────────────

@app.get("/clients/{client_id}/activity", tags=["Activities"])
async def get_client_activity(
    client_id: str,
    username: str = Depends(verify_credentials)
):
    """Get activity timeline for a client"""
    try:
        await sheets.require_client(client_id)
        activities = await sheets.get_client_activities(client_id)
        return {
            "ok": True,
            "client_id": client_id,
            "count": len(activities),
            "activities": activities
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/activities", tags=["Activities"])
async def search_activities(
    activity_type: Optional[str] = Query(None),
    client_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    username: str = Depends(verify_credentials)
):
    """Search all activities"""
    activities = await sheets.search_activities(
        activity_type=activity_type,
        client_id=client_id,
        limit=limit
    )
    return {"ok": True, "count": len(activities), "activities": activities}

# ─── Pipeline ──────────────────────────────────────────

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
    summary = await sheets.get_pipeline_summary()
    clients = await sheets.get_all_clients(limit=1000)
    report_bytes = generate_pipeline_report(summary, clients)

    return Response(
        content=report_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": "attachment; filename=pipeline_report.docx"
        }
    )

@app.get("/followups/due", tags=["Pipeline"])
async def followups_due(
    username: str = Depends(verify_credentials)
):
    """Get clients with follow-ups due today or overdue"""
    clients = await sheets.get_followups_due()
    return {"ok": True, "count": len(clients), "clients": clients}

# ─── Documents ─────────────────────────────────────────

@app.post("/process-pdf", tags=["Documents"])
async def process_pdf(
    file: UploadFile = File(...),
    username: str = Depends(verify_credentials)
):
    """Upload PDF, extract client data with AI, create client record"""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "File must be a PDF")

    try:
        file_bytes = await file.read()
        pdf_data = extract_pdf_text(file_bytes)

        if not pdf_data["raw_text"].strip():
            raise HTTPException(400, "Could not extract text from PDF")

        extracted = await extract_client_from_pdf(pdf_data["raw_text"])
        client = await sheets.create_client(extracted)

        await sheets.log_activity(
            client["client_id"], "PDF_PROCESSED",
            f"Created client from PDF: {file.filename}",
            "SUCCESS", ""
        )

        return {
            "ok": True,
            "message": "PDF processed and client created",
            "filename": file.filename,
            "pages_processed": pdf_data["page_count"],
            "client": client,
            "extracted_data": extracted
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"PDF processing failed: {e}")
        raise HTTPException(500, f"PDF processing failed: {str(e)}")

@app.post("/clients/{client_id}/report", tags=["Documents"])
async def generate_report(
    client_id: str,
    username: str = Depends(verify_credentials)
):
    """Generate Word document report for a client"""
    try:
        client = await sheets.require_client(client_id)
        analysis = await analyze_client(client)
        report_bytes = generate_client_report(client, analysis)

        await sheets.log_activity(
            client_id, "REPORT_GENERATED",
            f"Generated report for {client['name']}",
            "SUCCESS", ""
        )

        return Response(
            content=report_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": f"attachment; filename=report_{client_id}.docx"
            }
        )
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        logger.error(f"Report failed: {e}")
        raise HTTPException(500, str(e))

# ─── Email ─────────────────────────────────────────────

@app.post("/email/draft", tags=["Email"])
async def create_email_draft(
    data: EmailDraft,
    username: str = Depends(verify_credentials)
):
    """Create a Gmail draft"""
    try:
        settings = get_settings()
        client = await sheets.require_client(data.client_id)
        recipient = str(data.to) if data.to else client.get("email")

        if not recipient:
            raise HTTPException(400, "No recipient email")

        result = await create_draft(
            to=recipient,
            subject=data.subject,
            body=data.body,
            from_email=settings.gmail_address
        )

        await sheets.log_activity(
            data.client_id, "EMAIL_DRAFT_CREATED",
            f"Draft for {recipient}: {data.subject}",
            "SUCCESS", result.get("gmail_drafts_url", "")
        )

        return {"ok": True, "message": "Draft created", **result}
    except ValueError as e:
        raise HTTPException(400, str(e))

@app.post("/email/send", tags=["Email"])
async def send_email_endpoint(
    data: EmailSend,
    username: str = Depends(verify_credentials)
):
    """Send a real email via Gmail"""
    try:
        settings = get_settings()
        client = await sheets.require_client(data.client_id)
        recipient = str(data.to) if data.to else client.get("email")

        if not recipient:
            raise HTTPException(400, "No recipient email")

        result = await send_email(
            to=recipient,
            subject=data.subject,
            body=data.body,
            from_email=settings.gmail_address
        )

        await sheets.log_activity(
            data.client_id, "EMAIL_SENT",
            f"Sent to {recipient}: {data.subject}",
            "SUCCESS", ""
        )

        return {"ok": True, "message": "Email sent", **result}
    except ValueError as e:
        raise HTTPException(400, str(e))

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
    username: str = Depends(verify_credentials)
):
    """List Gmail drafts"""
    try:
        drafts = await list_drafts(max_results)
        return {"ok": True, "count": len(drafts), "drafts": drafts}
    except Exception as e:
        raise HTTPException(400, str(e))

# ─── AI Agent ──────────────────────────────────────────

@app.post("/agent/chat", tags=["Agent"])
async def agent_chat(
    data: AgentChat,
    username: str = Depends(verify_credentials)
):
    """Ask AI anything about your CRM"""
    try:
        response = await chat(data.message, data.client_id)
        await sheets.log_agent("CHAT", data.message, response)
        return {"ok": True, "message": data.message, "response": response}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/agent/analyze/{client_id}", tags=["Agent"])
async def agent_analyze(
    client_id: str,
    username: str = Depends(verify_credentials)
):
    """Deep AI analysis of a client"""
    try:
        client = await sheets.require_client(client_id)
        analysis = await analyze_client(client)
        await sheets.log_agent(
            "ANALYZE_CLIENT", client_id, str(analysis)
        )
        return {
            "ok": True,
            "client_id": client_id,
            "client_name": client.get("name"),
            "analysis": analysis
        }
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/agent/draft-email", tags=["Agent"])
async def agent_draft_email(
    data: AgentDraftEmail,
    username: str = Depends(verify_credentials)
):
    """AI drafts a professional email and saves to Gmail"""
    try:
        settings = get_settings()
        client = await sheets.require_client(data.client_id)
        drafted = await draft_email(client, data.instruction)

        recipient = client.get("email")
        if not recipient:
            raise HTTPException(400, "Client has no email")

        if data.send:
            result = await send_email(
                to=recipient,
                subject=drafted["subject"],
                body=drafted["body"],
                from_email=settings.gmail_address
            )
            await sheets.log_activity(
                data.client_id, "AI_EMAIL_SENT",
                f"AI sent email to {recipient}",
                "SUCCESS", ""
            )
            return {
                "ok": True,
                "message": "AI email sent",
                "subject": drafted["subject"],
                "body": drafted["body"],
                **result
            }
        else:
            result = await create_draft(
                to=recipient,
                subject=drafted["subject"],
                body=drafted["body"],
                from_email=settings.gmail_address
            )
            await sheets.log_activity(
                data.client_id, "AI_EMAIL_DRAFT_CREATED",
                f"AI drafted email for {recipient}",
                "SUCCESS", result.get("gmail_drafts_url", "")
            )
            return {
                "ok": True,
                "message": "AI email draft saved to Gmail",
                "subject": drafted["subject"],
                "body": drafted["body"],
                **result
            }
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))

# ─── Calendar ──────────────────────────────────────────

@app.post("/meetings", tags=["Calendar"])
async def create_meeting(
    data: ScheduleMeetingInput,
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

        await sheets.log_activity(
            data.client_id,
            "MEETING_SCHEDULED",
            f"Meeting: {result['title']} at {result['start_time']}",
            "SUCCESS",
            result.get("calendar_link", "")
        )

        await sheets.update_next_followup(
            data.client_id,
            data.start_time[:10]
        )

        return {
            "ok": True,
            "message": "Meeting scheduled",
            "client_id": data.client_id,
            **result
        }
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"Meeting scheduling failed: {e}")
        raise HTTPException(500, str(e))

@app.get("/meetings", tags=["Calendar"])
async def upcoming_meetings(
    days_ahead: int = Query(7, ge=1, le=90),
    max_results: int = Query(10, ge=1, le=50),
    username: str = Depends(verify_credentials)
):
    """Get upcoming meetings"""
    try:
        meetings = await get_upcoming_meetings(
            days_ahead=days_ahead,
            max_results=max_results
        )
        return {
            "ok": True,
            "count": len(meetings),
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
    data: UpdateMeetingInput,
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
    event_id: str,
    notify_attendees: bool = Query(True),
    username: str = Depends(verify_credentials)
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
    data: MeetingNotesInput,
    username: str = Depends(verify_credentials)
):
    """Add notes to an existing meeting"""
    try:
        result = await add_meeting_notes(event_id, data.notes)
        return {
            "ok": True,
            "message": "Notes added to meeting",
            **result
        }
    except Exception as e:
        raise HTTPException(400, str(e))

@app.get("/clients/{client_id}/meetings", tags=["Calendar"])
async def get_meetings_for_client(
    client_id: str,
    days_back: int = Query(30, ge=0, le=365),
    days_ahead: int = Query(30, ge=0, le=365),
    username: str = Depends(verify_credentials)
):
    """Get all meetings involving a specific client"""
    try:
        client = await sheets.require_client(client_id)

        if not client.get("email"):
            raise HTTPException(
                400,
                "Client has no email — "
                "cannot search calendar meetings"
            )

        meetings = await get_client_meetings(
            client_email=client["email"],
            days_back=days_back,
            days_ahead=days_ahead
        )

        return {
            "ok": True,
            "client_id": client_id,
            "count": len(meetings),
            "meetings": meetings
        }
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))

# ─── Lead Scoring & Recommendations ───────────────────

@app.get("/clients/{client_id}/score", tags=["Intelligence"])
async def score_client_endpoint(
    client_id: str,
    username: str = Depends(verify_credentials)
):
    """
    AI scores a client on lead quality, churn risk,
    sentiment, opportunity value and recommends actions
    """
    try:
        client = await sheets.require_client(client_id)
        score = await score_single_client(client)

        await sheets.log_activity(
            client_id,
            "CLIENT_SCORED",
            f"Lead score: {score.get('lead_score')}/10 | "
            f"Churn risk: {score.get('churn_risk')} | "
            f"Close probability: {score.get('estimated_close_probability')}%",
            "SUCCESS",
            ""
        )

        await sheets.log_agent(
            "LEAD_SCORING",
            client_id,
            str(score)
        )

        return {
            "ok": True,
            "client_id": client_id,
            "client_name": client.get("name"),
            "score": score
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
    """
    AI analyzes entire pipeline health,
    identifies at-risk clients and stalled deals
    """
    try:
        clients = await sheets.get_all_clients(limit=1000)

        if not clients:
            raise HTTPException(400, "No clients in pipeline")

        analysis = await score_entire_pipeline(clients)

        await sheets.log_agent(
            "PIPELINE_SCORING",
            f"Scored {len(clients)} clients",
            str(analysis)
        )

        return {
            "ok": True,
            "total_clients_analyzed": len(clients),
            "analysis": analysis
        }
    except Exception as e:
        logger.error(f"Pipeline scoring failed: {e}")
        raise HTTPException(500, str(e))

@app.get("/clients/{client_id}/similar", tags=["Intelligence"])
async def find_similar_clients_endpoint(
    client_id: str,
    username: str = Depends(verify_credentials)
):
    """Find clients similar to a target client"""
    try:
        target = await sheets.require_client(client_id)
        all_clients = await sheets.get_all_clients(limit=1000)

        result = await find_similar_clients(target, all_clients)

        return {
            "ok": True,
            "client_id": client_id,
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
    """
    AI recommends which clients to follow up with today
    and suggests a daily action plan
    """
    try:
        clients = await sheets.get_all_clients(limit=1000)

        if not clients:
            raise HTTPException(400, "No clients found")

        recommendations = await get_daily_recommendations(clients)

        await sheets.log_agent(
            "DAILY_RECOMMENDATIONS",
            f"Generated for {len(clients)} clients",
            str(recommendations)
        )

        return {
            "ok": True,
            "total_clients": len(clients),
            "recommendations": recommendations
        }
    except Exception as e:
        logger.error(f"Daily recommendations failed: {e}")
        raise HTTPException(500, str(e))

@app.get("/recommendations/stale", tags=["Intelligence"])
async def stale_clients(
    days_inactive: int = Query(14, ge=1, le=365),
    username: str = Depends(verify_credentials)
):
    """
    Find clients with no activity for X days
    """
    try:
        from datetime import datetime, timedelta

        all_activities = await sheets.search_activities(
            limit=1000
        )

        cutoff = (
            datetime.utcnow() - timedelta(days=days_inactive)
        ).isoformat()

        active_client_ids = set(
            a["client_id"]
            for a in all_activities
            if a.get("timestamp", "") >= cutoff
        )

        all_clients = await sheets.get_all_clients(limit=1000)

        stale = [
            c for c in all_clients
            if c["client_id"] not in active_client_ids
            and c.get("stage") not in ["Won", "Lost"]
        ]

        return {
            "ok": True,
            "days_inactive": days_inactive,
            "stale_count": len(stale),
            "stale_clients": stale
        }
    except Exception as e:
        raise HTTPException(500, str(e))

# ─── Contracts, Invoices, Proposals ───────────────────

@app.post("/clients/{client_id}/contract", tags=["Documents"])
async def create_contract(
    client_id: str,
    data: GenerateContractInput,
    username: str = Depends(verify_credentials)
):
    """Generate a professional service contract"""
    try:
        client = await sheets.require_client(client_id)

        import uuid
        contract_data = data.model_dump()
        contract_data["contract_number"] = (
            "CON-" + str(uuid.uuid4())[:8].upper()
        )

        contract_bytes = generate_contract(client, contract_data)

        await sheets.log_activity(
            client_id,
            "CONTRACT_GENERATED",
            f"Contract generated for {client['name']}",
            "SUCCESS",
            ""
        )

        filename = f"contract_{client_id}.docx"

        return Response(
            content=contract_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        logger.error(f"Contract generation failed: {e}")
        raise HTTPException(500, str(e))

@app.post("/clients/{client_id}/invoice", tags=["Documents"])
async def create_invoice(
    client_id: str,
    data: GenerateInvoiceInput,
    username: str = Depends(verify_credentials)
):
    """Generate a professional invoice"""
    try:
        client = await sheets.require_client(client_id)

        invoice_data = data.model_dump()
        invoice_data["line_items"] = [
            item if isinstance(item, dict)
            else item.model_dump()
            for item in data.line_items
        ]

        invoice_bytes = generate_invoice(client, invoice_data)

        await sheets.log_activity(
            client_id,
            "INVOICE_GENERATED",
            f"Invoice generated for {client['name']}",
            "SUCCESS",
            ""
        )

        filename = f"invoice_{client_id}.docx"

        return Response(
            content=invoice_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        logger.error(f"Invoice generation failed: {e}")
        raise HTTPException(500, str(e))

@app.post("/clients/{client_id}/proposal", tags=["Documents"])
async def create_proposal(
    client_id: str,
    data: GenerateProposalInput,
    username: str = Depends(verify_credentials)
):
    """Generate a professional business proposal"""
    try:
        client = await sheets.require_client(client_id)
        proposal_data = data.model_dump()
        proposal_bytes = generate_proposal(client, proposal_data)

        await sheets.log_activity(
            client_id,
            "PROPOSAL_GENERATED",
            f"Proposal generated for {client['name']}",
            "SUCCESS",
            ""
        )

        await sheets.update_stage(
            client_id,
            "Proposal Sent",
            changed_by=username
        )

        filename = f"proposal_{client_id}.docx"

        return Response(
            content=proposal_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        logger.error(f"Proposal generation failed: {e}")
        raise HTTPException(500, str(e))

@app.post("/clients/{client_id}/ai-proposal", tags=["Documents"])
async def ai_generate_proposal(
    client_id: str,
    provider_name: str,
    provider_email: Optional[str] = None,
    username: str = Depends(verify_credentials)
):
    """
    AI automatically generates a complete proposal
    based on client data — no manual input needed
    """
    try:
        client = await sheets.require_client(client_id)
        analysis = await analyze_client(client)

        proposal_data = {
            "provider_name": provider_name,
            "provider_email": provider_email,
            "executive_summary": analysis.get(
                "executive_summary", ""
            ),
            "problem_statement": analysis.get(
                "business_problem", ""
            ),
            "proposed_solution": (
                f"We propose to address your "
                f"{client.get('service', 'needs')} through "
                f"our proven methodology and expertise."
            ),
            "scope_items": analysis.get(
                "recommendations", []
            ),
            "next_steps": [
                "Review this proposal",
                "Schedule a discovery call",
                "Sign the service agreement",
                "Begin project kickoff"
            ],
            "why_us": [
                "Proven track record",
                "Dedicated support team",
                "Transparent pricing",
                "On-time delivery guarantee"
            ]
        }

        proposal_bytes = generate_proposal(
            client, proposal_data
        )

        await sheets.log_activity(
            client_id,
            "AI_PROPOSAL_GENERATED",
            f"AI generated proposal for {client['name']}",
            "SUCCESS",
            ""
        )

        filename = f"ai_proposal_{client_id}.docx"

        return Response(
            content=proposal_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        logger.error(f"AI proposal failed: {e}")
        raise HTTPException(500, str(e))