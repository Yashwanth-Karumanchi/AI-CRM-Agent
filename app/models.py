from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List
from enum import Enum
from datetime import datetime

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

class ClientUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    company: Optional[str] = None
    phone: Optional[str] = None
    service: Optional[str] = None
    priority: Optional[Priority] = None
    notes: Optional[str] = None

class StageUpdate(BaseModel):
    stage: Stage

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

class APIResponse(BaseModel):
    ok: bool
    message: str
    data: Optional[dict] = None
    error: Optional[str] = None