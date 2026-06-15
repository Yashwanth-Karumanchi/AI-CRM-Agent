from fastapi import (
    FastAPI, Depends, UploadFile,
    File, HTTPException, Query
)
from fastapi.responses import Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import json

from app.auth import verify_credentials
from app.models import (
    ClientCreate, ClientUpdate, StageUpdate,
    EmailDraft, EmailSend, AgentChat, APIResponse
)
from app.config import get_settings
from app.logger import get_logger
from app.services import sheets
from app.services.document import generate_client_report, generate_pipeline_report
from app.services.pdf import extract_pdf_text
from app.services.gmail import send_email, create_draft
from app.agent import (
    extract_client_from_pdf,
    analyze_client,
    draft_email,
    chat
)

logger = get_logger(__name__)

app = FastAPI(
    title="AI CRM Agent",
    description="Production-ready AI CRM Agent using FastAPI, Gemini, Google Sheets, Gmail and MCP",
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

# --- Startup ---

@app.on_event("startup")
async def startup():
    logger.info("Starting AI CRM Agent")
    try:
        sheets.setup_sheets()
        logger.info("Google Sheets initialized")
    except Exception as e:
        logger.error(f"Sheets setup failed: {e}")

@app.get("/debug-gmail", tags=["System"])
async def debug_gmail():
    import os
    import json
    token_env = os.getenv("GMAIL_TOKEN")
    return {
        "gmail_token_exists": token_env is not None,
        "gmail_token_length": len(token_env) if token_env else 0,
        "gmail_address": os.getenv("GMAIL_ADDRESS"),
        "has_refresh_token": "refresh_token" in (token_env or "")
    }
    
# --- Health ---

@app.get("/health", tags=["System"])
async def health():
    return {
        "ok": True,
        "service": "AI CRM Agent",
        "version": "1.0.0"
    }

# --- Clients ---

@app.post("/clients", tags=["Clients"])
async def create_client(
    data: ClientCreate,
    username: str = Depends(verify_credentials)
):
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
    limit: int = Query(20, ge=1, le=50),
    username: str = Depends(verify_credentials)
):
    clients = await sheets.get_all_clients(
        query=query,
        stage=stage,
        priority=priority,
        client_id=client_id,
        email=email,
        limit=limit
    )
    return {"ok": True, "count": len(clients), "clients": clients}

@app.get("/clients/{client_id}", tags=["Clients"])
async def get_client(
    client_id: str,
    username: str = Depends(verify_credentials)
):
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
    try:
        updates = data.model_dump(exclude_none=True)
        if not updates:
            raise HTTPException(
                status_code=400,
                detail="No fields to update"
            )
        client = await sheets.update_client(client_id, updates)
        return {"ok": True, "message": "Client updated", "client": client}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.put("/clients/{client_id}/stage", tags=["Clients"])
async def update_stage(
    client_id: str,
    data: StageUpdate,
    username: str = Depends(verify_credentials)
):
    try:
        result = await sheets.update_stage(client_id, data.stage.value)
        return {"ok": True, "message": "Stage updated", **result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.delete("/clients/{client_id}", tags=["Clients"])
async def archive_client(
    client_id: str,
    username: str = Depends(verify_credentials)
):
    try:
        result = await sheets.archive_client(client_id)
        return {"ok": True, "message": "Client archived", **result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/clients/{client_id}/activity", tags=["Clients"])
async def get_client_activity(
    client_id: str,
    username: str = Depends(verify_credentials)
):
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

# --- PDF Processing ---

@app.post("/process-pdf", tags=["Documents"])
async def process_pdf(
    file: UploadFile = File(...),
    username: str = Depends(verify_credentials)
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="File must be a PDF"
        )

    try:
        file_bytes = await file.read()
        pdf_data = extract_pdf_text(file_bytes)

        if not pdf_data["raw_text"].strip():
            raise HTTPException(
                status_code=400,
                detail="Could not extract text from PDF"
            )

        extracted = await extract_client_from_pdf(
            pdf_data["raw_text"]
        )

        client = await sheets.create_client(extracted)

        await sheets.log_activity(
            client["client_id"],
            "PDF_PROCESSED",
            f"Created client from PDF: {file.filename}",
            "SUCCESS",
            ""
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
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"PDF processing failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"PDF processing failed: {str(e)}"
        )

# --- Reports ---

@app.post("/clients/{client_id}/report", tags=["Documents"])
async def generate_report(
    client_id: str,
    username: str = Depends(verify_credentials)
):
    try:
        client = await sheets.require_client(client_id)
        analysis = await analyze_client(client)
        report_bytes = generate_client_report(client, analysis)

        await sheets.log_activity(
            client_id,
            "REPORT_GENERATED",
            f"Generated Word report for {client['name']}",
            "SUCCESS",
            ""
        )

        filename = f"report_{client_id}.docx"

        return Response(
            content=report_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Report generation failed: {str(e)}"
        )

@app.get("/pipeline/report", tags=["Documents"])
async def generate_pipeline_report(
    username: str = Depends(verify_credentials)
):
    try:
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
    except Exception as e:
        logger.error(f"Pipeline report failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline report failed: {str(e)}"
        )

# --- Pipeline ---

@app.get("/pipeline", tags=["Pipeline"])
async def get_pipeline(
    username: str = Depends(verify_credentials)
):
    try:
        summary = await sheets.get_pipeline_summary()
        return {"ok": True, **summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Email ---

@app.post("/email/draft", tags=["Email"])
async def create_email_draft(
    data: EmailDraft,
    username: str = Depends(verify_credentials)
):
    try:
        settings = get_settings()
        client = await sheets.require_client(data.client_id)

        recipient = str(data.to) if data.to else client.get("email")
        if not recipient:
            raise HTTPException(
                status_code=400,
                detail="No recipient email available"
            )

        result = await create_draft(
            to=recipient,
            subject=data.subject,
            body=data.body,
            from_email=settings.gmail_address
        )

        await sheets.log_activity(
            data.client_id,
            "EMAIL_DRAFT_CREATED",
            f"Created draft for {recipient}: {data.subject}",
            "SUCCESS",
            result.get("gmail_drafts_url", "")
        )

        return {"ok": True, "message": "Draft created in Gmail", **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/email/send", tags=["Email"])
async def send_email_endpoint(
    data: EmailSend,
    username: str = Depends(verify_credentials)
):
    try:
        settings = get_settings()
        client = await sheets.require_client(data.client_id)

        recipient = str(data.to) if data.to else client.get("email")
        if not recipient:
            raise HTTPException(
                status_code=400,
                detail="No recipient email available"
            )

        result = await send_email(
            to=recipient,
            subject=data.subject,
            body=data.body,
            from_email=settings.gmail_address
        )

        await sheets.log_activity(
            data.client_id,
            "EMAIL_SENT",
            f"Sent email to {recipient}: {data.subject}",
            "SUCCESS",
            ""
        )

        return {"ok": True, "message": "Email sent successfully", **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# --- AI Agent ---

@app.post("/agent/chat", tags=["Agent"])
async def agent_chat(
    data: AgentChat,
    username: str = Depends(verify_credentials)
):
    try:
        response = await chat(data.message, data.client_id)

        await sheets.log_agent(
            "CHAT",
            data.message,
            response
        )

        return {
            "ok": True,
            "message": data.message,
            "response": response
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/agent/draft-email", tags=["Agent"])
async def agent_draft_email(
    data: EmailDraft,
    username: str = Depends(verify_credentials)
):
    try:
        settings = get_settings()
        client = await sheets.require_client(data.client_id)

        drafted = await draft_email(client, data.body)

        recipient = str(data.to) if data.to else client.get("email")
        if not recipient:
            raise HTTPException(
                status_code=400,
                detail="No recipient email available"
            )

        result = await create_draft(
            to=recipient,
            subject=drafted["subject"],
            body=drafted["body"],
            from_email=settings.gmail_address
        )

        await sheets.log_activity(
            data.client_id,
            "AI_EMAIL_DRAFT_CREATED",
            f"AI drafted email for {recipient}",
            "SUCCESS",
            result.get("gmail_drafts_url", "")
        )

        return {
            "ok": True,
            "message": "AI drafted email and saved to Gmail drafts",
            "subject": drafted["subject"],
            "body": drafted["body"],
            "draft_for": recipient,
            **result
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/agent/analyze/{client_id}", tags=["Agent"])
async def agent_analyze(
    client_id: str,
    username: str = Depends(verify_credentials)
):
    try:
        client = await sheets.require_client(client_id)
        analysis = await analyze_client(client)

        await sheets.log_agent(
            "ANALYZE_CLIENT",
            client_id,
            str(analysis)
        )

        return {
            "ok": True,
            "client_id": client_id,
            "client_name": client.get("name"),
            "analysis": analysis
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))