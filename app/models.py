from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List
from enum import Enum
from datetime import datetime, date

class Priority(str, Enum):
    low = "Low"
    medium = "Medium"
    high = "High"

class Stage(str, Enum):
    new = "New"
    contacted = "Contacted"
    consultation_scheduled = "Consultation Scheduled"
    proposal_sent = "Proposal Sent"
    won = "Won"
    lost = "Lost"

class ClientCreate(BaseModel):
    name: str
    email: Optional[EmailStr] = None
    company: Optional[str] = None
    phone: Optional[str] = None
    service: Optional[str] = None
    priority: Priority = Priority.medium
    stage: Stage = Stage.new
    notes: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Name cannot be empty")
        return v.strip()

    @field_validator("company", "phone", "service", "notes", mode="before")
    @classmethod
    def strip_strings(cls, v):
        if isinstance(v, str):
            return v.strip() or None
        return v

class ClientUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    company: Optional[str] = None
    phone: Optional[str] = None
    service: Optional[str] = None
    priority: Optional[Priority] = None
    notes: Optional[str] = None

    @field_validator("name", mode="before")
    @classmethod
    def name_not_empty(cls, v):
        if v is not None and not str(v).strip():
            raise ValueError("Name cannot be empty")
        return v

class StageUpdate(BaseModel):
    stage: Stage

class FollowUpUpdate(BaseModel):
    follow_up_date: str

    @field_validator("follow_up_date")
    @classmethod
    def must_be_valid_date(cls, v):
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("follow_up_date must be YYYY-MM-DD")
        return v

class BulkStageUpdate(BaseModel):
    client_ids: List[str]
    stage: Stage

    @field_validator("client_ids")
    @classmethod
    def must_not_be_empty(cls, v):
        if not v:
            raise ValueError("client_ids cannot be empty")
        return v

class BulkArchive(BaseModel):
    client_ids: List[str]

    @field_validator("client_ids")
    @classmethod
    def must_not_be_empty(cls, v):
        if not v:
            raise ValueError("client_ids cannot be empty")
        return v

class EmailDraft(BaseModel):
    client_id: str
    subject: str
    body: str
    to: Optional[EmailStr] = None

    @field_validator("subject", "body")
    @classmethod
    def not_empty(cls, v):
        if not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()

class EmailSend(BaseModel):
    client_id: str
    subject: str
    body: str
    to: Optional[EmailStr] = None

    @field_validator("subject", "body")
    @classmethod
    def not_empty(cls, v):
        if not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()

class AgentChat(BaseModel):
    message: str
    client_id: Optional[str] = None

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Message cannot be empty")
        return v.strip()

class AgentDraftEmail(BaseModel):
    client_id: str
    instruction: str
    send: bool = False

    @field_validator("instruction")
    @classmethod
    def not_empty(cls, v):
        if not v.strip():
            raise ValueError("Instruction cannot be empty")
        return v.strip()

class DeleteDraftInput(BaseModel):
    draft_id: str

class APIResponse(BaseModel):
    ok: bool
    message: str
    data: Optional[dict] = None
    error: Optional[str] = None
    
class ScheduleMeetingInput(BaseModel):
    client_id: str
    title: Optional[str] = None
    start_time: str
    end_time: str
    description: Optional[str] = None
    location: Optional[str] = None
    invite_client: bool = False
    meeting_notes: Optional[str] = None

    @field_validator("start_time", "end_time")
    @classmethod
    def must_be_iso(cls, v):
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError(
                "Must be ISO 8601 format: "
                "2026-06-15T15:00:00-06:00"
            )
        return v

class UpdateMeetingInput(BaseModel):
    title: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    meeting_notes: Optional[str] = None

class MeetingNotesInput(BaseModel):
    notes: str

    @field_validator("notes")
    @classmethod
    def not_empty(cls, v):
        if not v.strip():
            raise ValueError("Notes cannot be empty")
        return v.strip()

class TimelineItem(BaseModel):
    milestone: Optional[str] = None
    phase: Optional[str] = None
    description: Optional[str] = None
    date: Optional[str] = None
    duration: Optional[str] = None

class LineItem(BaseModel):
    description: str
    quantity: float = 1.0
    unit_price: float = 0.0

class PricingTier(BaseModel):
    name: str
    price: str
    description: Optional[str] = None
    includes: Optional[List[str]] = None

class GenerateContractInput(BaseModel):
    client_id: str
    provider_name: str
    provider_address: Optional[str] = None
    provider_email: Optional[str] = None
    scope_of_work: Optional[str] = None
    deliverables: Optional[List[str]] = None
    timeline: Optional[List[TimelineItem]] = None
    total_amount: Optional[str] = None
    payment_schedule: Optional[str] = "Net 30"
    payment_method: Optional[str] = "Bank Transfer"
    valid_until: Optional[str] = None
    terms: Optional[List[str]] = None
    confidentiality: Optional[str] = None
    ip_clause: Optional[str] = None

class GenerateInvoiceInput(BaseModel):
    client_id: str
    provider_name: str
    provider_email: Optional[str] = None
    provider_address: Optional[str] = None
    line_items: List[LineItem]
    tax_rate: float = 0.0
    discount: float = 0.0
    due_date: Optional[str] = None
    payment_instructions: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("line_items")
    @classmethod
    def must_have_items(cls, v):
        if not v:
            raise ValueError("Must have at least one line item")
        return v

class GenerateProposalInput(BaseModel):
    client_id: str
    provider_name: str
    provider_email: Optional[str] = None
    executive_summary: Optional[str] = None
    problem_statement: Optional[str] = None
    proposed_solution: Optional[str] = None
    scope_items: Optional[List[str]] = None
    timeline: Optional[List[TimelineItem]] = None
    total_price: Optional[str] = None
    pricing_tiers: Optional[List[PricingTier]] = None
    pricing_notes: Optional[str] = None
    why_us: Optional[List[str]] = None
    next_steps: Optional[List[str]] = None
    call_to_action: Optional[str] = None
    valid_until: Optional[str] = None