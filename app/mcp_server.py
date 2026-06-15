try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    from fastmcp import FastMCP
from pydantic import BaseModel, EmailStr
from typing import Optional, List
import json
from app.services import sheets, pdf, gmail
from app.services.document import generate_client_report, generate_pipeline_report
from app.agent import (
    extract_client_from_pdf,
    analyze_client,
    draft_email,
    chat
)
from app.logger import get_logger

logger = get_logger(__name__)

mcp = FastMCP("AI CRM Agent")

# --- Input Models ---

class CreateClientInput(BaseModel):
    name: str
    email: Optional[EmailStr] = None
    company: Optional[str] = None
    phone: Optional[str] = None
    service: Optional[str] = None
    priority: str = "Medium"
    stage: str = "New"
    notes: Optional[str] = None

class FindClientsInput(BaseModel):
    query: Optional[str] = None
    client_id: Optional[str] = None
    email: Optional[str] = None
    stage: Optional[str] = None
    priority: Optional[str] = None
    limit: int = 20

class UpdateStageInput(BaseModel):
    client_id: str
    stage: str

class UpdateClientInput(BaseModel):
    client_id: str
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    company: Optional[str] = None
    phone: Optional[str] = None
    service: Optional[str] = None
    priority: Optional[str] = None
    notes: Optional[str] = None

class ArchiveClientInput(BaseModel):
    client_id: str

class GenerateReportInput(BaseModel):
    client_id: str
    executive_summary: Optional[str] = None
    business_problem: Optional[str] = None
    current_process: Optional[str] = None
    recommendations: Optional[List[str]] = None
    open_questions: Optional[List[str]] = None
    notes: Optional[str] = None

class EmailDraftInput(BaseModel):
    client_id: str
    instruction: str
    send: bool = False

class SendEmailInput(BaseModel):
    client_id: str
    to: EmailStr
    subject: str
    body: str

class ChatInput(BaseModel):
    message: str
    client_id: Optional[str] = None

class AnalyzeClientInput(BaseModel):
    client_id: str

# --- MCP Tools ---

@mcp.tool()
async def check_health() -> dict:
    """Check whether the CRM agent is running"""
    return {
        "ok": True,
        "service": "AI CRM Agent",
        "version": "1.0.0"
    }

@mcp.tool()
async def create_client(data: CreateClientInput) -> dict:
    """
    Create a new client record in Google Sheets.
    Validates email, checks duplicates, logs activity.
    """
    try:
        client = await sheets.create_client(data.model_dump())
        return {"ok": True, "message": "Client created", "client": client}
    except ValueError as e:
        return {"ok": False, "error": str(e)}

@mcp.tool()
async def find_clients(filters: FindClientsInput) -> dict:
    """
    Search and filter client records.
    Supports text search, stage, priority, email filters.
    """
    try:
        clients = await sheets.get_all_clients(
            query=filters.query,
            stage=filters.stage,
            priority=filters.priority,
            client_id=filters.client_id,
            email=filters.email,
            limit=filters.limit
        )
        return {"ok": True, "count": len(clients), "clients": clients}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@mcp.tool()
async def get_client(client_id: str) -> dict:
    """Get a single client by ID"""
    try:
        client = await sheets.require_client(client_id)
        return {"ok": True, "client": client}
    except ValueError as e:
        return {"ok": False, "error": str(e)}

@mcp.tool()
async def update_client(data: UpdateClientInput) -> dict:
    """Update client information"""
    try:
        updates = data.model_dump(exclude={"client_id"}, exclude_none=True)
        client = await sheets.update_client(data.client_id, updates)
        return {"ok": True, "message": "Client updated", "client": client}
    except ValueError as e:
        return {"ok": False, "error": str(e)}

@mcp.tool()
async def update_client_stage(data: UpdateStageInput) -> dict:
    """Move a client to a new pipeline stage"""
    try:
        result = await sheets.update_stage(data.client_id, data.stage)
        return {"ok": True, "message": "Stage updated", **result}
    except ValueError as e:
        return {"ok": False, "error": str(e)}

@mcp.tool()
async def archive_client(data: ArchiveClientInput) -> dict:
    """Archive a client record"""
    try:
        result = await sheets.archive_client(data.client_id)
        return {"ok": True, "message": "Client archived", **result}
    except ValueError as e:
        return {"ok": False, "error": str(e)}

@mcp.tool()
async def get_pipeline_summary() -> dict:
    """Get pipeline stats, stage counts and high priority clients"""
    try:
        summary = await sheets.get_pipeline_summary()
        return {"ok": True, **summary}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@mcp.tool()
async def get_client_activities(client_id: str) -> dict:
    """Get full activity timeline for a client"""
    try:
        activities = await sheets.get_client_activities(client_id)
        return {
            "ok": True,
            "client_id": client_id,
            "count": len(activities),
            "activities": activities
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

@mcp.tool()
async def generate_client_report(data: GenerateReportInput) -> dict:
    """Generate a Word document intake report for a client"""
    try:
        client = await sheets.require_client(data.client_id)
        analysis = data.model_dump(exclude={"client_id"})
        report_bytes = generate_client_report(client, analysis)

        filename = f"report_{data.client_id}.docx"
        with open(filename, "wb") as f:
            f.write(report_bytes)

        await sheets.log_activity(
            data.client_id,
            "REPORT_GENERATED",
            f"Generated Word report for {client['name']}",
            "SUCCESS",
            filename
        )

        return {
            "ok": True,
            "message": "Report generated",
            "client_id": data.client_id,
            "filename": filename
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

@mcp.tool()
async def ai_draft_email(data: EmailDraftInput) -> dict:
    """
    Use AI to draft a professional email for a client.
    Optionally send it immediately or save as Gmail draft.
    """
    try:
        from app.config import get_settings
        settings = get_settings()

        client = await sheets.require_client(data.client_id)
        drafted = await draft_email(client, data.instruction)

        recipient = client.get("email")
        if not recipient:
            return {
                "ok": False,
                "error": "Client has no email address"
            }

        if data.send:
            result = await gmail.send_email(
                to=recipient,
                subject=drafted["subject"],
                body=drafted["body"],
                from_email=settings.gmail_address
            )
            await sheets.log_activity(
                data.client_id,
                "EMAIL_SENT",
                f"Sent email to {recipient}: {drafted['subject']}",
                "SUCCESS",
                ""
            )
            return {
                "ok": True,
                "message": "Email sent successfully",
                "subject": drafted["subject"],
                "body": drafted["body"],
                "sent_to": recipient,
                **result
            }
        else:
            result = await gmail.create_draft(
                to=recipient,
                subject=drafted["subject"],
                body=drafted["body"],
                from_email=settings.gmail_address
            )
            await sheets.log_activity(
                data.client_id,
                "EMAIL_DRAFT_CREATED",
                f"Created draft for {recipient}: {drafted['subject']}",
                "SUCCESS",
                result.get("gmail_drafts_url", "")
            )
            return {
                "ok": True,
                "message": "Draft created in Gmail",
                "subject": drafted["subject"],
                "body": drafted["body"],
                "draft_for": recipient,
                **result
            }
    except Exception as e:
        return {"ok": False, "error": str(e)}

@mcp.tool()
async def send_email(data: SendEmailInput) -> dict:
    """Send a real email via Gmail"""
    try:
        from app.config import get_settings
        settings = get_settings()

        client = await sheets.require_client(data.client_id)

        result = await gmail.send_email(
            to=str(data.to),
            subject=data.subject,
            body=data.body,
            from_email=settings.gmail_address
        )

        await sheets.log_activity(
            data.client_id,
            "EMAIL_SENT",
            f"Sent email to {data.to}: {data.subject}",
            "SUCCESS",
            ""
        )

        return {
            "ok": True,
            "message": "Email sent successfully",
            **result
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

@mcp.tool()
async def ai_chat(data: ChatInput) -> dict:
    """Ask the AI anything about your CRM data"""
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
        return {"ok": False, "error": str(e)}

@mcp.tool()
async def ai_analyze_client(data: AnalyzeClientInput) -> dict:
    """Deep AI analysis of a single client"""
    try:
        client = await sheets.require_client(data.client_id)
        analysis = await analyze_client(client)

        await sheets.log_agent(
            "ANALYZE_CLIENT",
            data.client_id,
            str(analysis)
        )

        return {
            "ok": True,
            "client_id": data.client_id,
            "client_name": client.get("name"),
            "analysis": analysis
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}