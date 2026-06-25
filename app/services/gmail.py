import os
import base64
import re
import json
import asyncio
from typing import List
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from app.logger import get_logger

logger = get_logger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.drafts",
    "https://www.googleapis.com/auth/gmail.modify"
]

SENDER_NAME = "Yashwanth Karumanchi"


def enforce_email_signature(body: str) -> str:
    """
    Ensure email ends with exactly one clean signature:
    Best regards,
    <sender name>

    Handles duplicates like:
    Best,
    Aria

    Best regards,
    Aria
    """
    body = (body or "").strip()
    default_sender = os.getenv("SENDER_NAME", "Aria").strip() or "Aria"

    if not body:
        return f"Best regards,\n{default_sender}"

    sender_name = default_sender

    # Remove trailing signature blocks repeatedly.
    # Handles:
    # Best,
    # Aria
    #
    # Best regards,
    # Aria
    signature_pattern = re.compile(
        r"(?is)\s*"
        r"(best|best\s+regards|kind\s+regards|warm\s+regards|regards|sincerely|thanks|thank\s+you)"
        r"\s*[,\.]?"
        r"(?:\s*\n+\s*([A-Za-z][A-Za-z\s\.\-']{0,80}))?"
        r"\s*$"
    )

    while True:
        match = signature_pattern.search(body)
        if not match:
            break

        found_name = match.group(2)
        if found_name:
            sender_name = found_name.strip()

        body = body[:match.start()].strip()

    return f"{body}\n\nBest regards,\n{sender_name}"

# ── Cached service ─────────────────────────────────────
_gmail_service = None
_gmail_service_ts = 0
_SERVICE_TTL = 3600


def _build_gmail_service_sync():
    """Build Gmail service — sync, runs in thread pool"""
    global _gmail_service, _gmail_service_ts

    import time
    now = time.time()
    if (_gmail_service is not None and
            now - _gmail_service_ts < _SERVICE_TTL):
        return _gmail_service

    creds = None
    token_env = os.getenv("GMAIL_TOKEN")

    if token_env:
        try:
            token_data = json.loads(token_env)
            creds = Credentials(
                token=token_data.get("token"),
                refresh_token=token_data.get("refresh_token"),
                token_uri=token_data.get(
                    "token_uri",
                    "https://oauth2.googleapis.com/token"
                ),
                client_id=token_data.get("client_id"),
                client_secret=token_data.get("client_secret"),
                scopes=token_data.get("scopes", SCOPES)
            )
        except Exception as e:
            logger.error(f"Failed to parse GMAIL_TOKEN: {e}")
            raise ValueError(
                f"Invalid GMAIL_TOKEN format: {e}"
            )
    elif os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file(
            "token.json", SCOPES
        )
    else:
        raise ValueError(
            "No Gmail credentials found. "
            "Set GMAIL_TOKEN environment variable."
        )

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            logger.info("Gmail token refreshed successfully")
        except Exception as e:
            raise ValueError(
                f"Gmail token refresh failed: {e}. "
                f"Please update GMAIL_TOKEN in Render."
            )

    if not creds or not creds.valid:
        raise ValueError(
            "Gmail credentials are invalid or expired. "
            "Please update GMAIL_TOKEN in Render."
        )

    service = build(
        "gmail", "v1",
        credentials=creds,
        cache_discovery=False
    )
    _gmail_service = service
    _gmail_service_ts = now
    return service


def _build_message(
    to: str,
    subject: str,
    body: str,
    from_email: str
) -> dict:
    """Build a MIME email message"""
    body = enforce_email_signature(body)

    message = MIMEMultipart("alternative")
    message["to"] = to
    message["from"] = from_email
    message["subject"] = subject

    # Plain text
    message.attach(MIMEText(body, "plain"))

    # HTML version
    html = "<html><body>"
    for line in body.split("\n"):
        if line.strip():
            html += f"<p>{line}</p>"
        else:
            html += "<br>"
    html += "</body></html>"
    message.attach(MIMEText(html, "html"))

    raw = base64.urlsafe_b64encode(
        message.as_bytes()
    ).decode("utf-8")
    return {"raw": raw}


# ── Send ───────────────────────────────────────────────

async def send_email(
    to: str,
    subject: str,
    body: str,
    from_email: str
) -> dict:
    """Send a real email via Gmail — non-blocking"""

    def _sync():
        service = _build_gmail_service_sync()
        msg = _build_message(to, subject, body, from_email)
        sent = service.users().messages().send(
            userId="me",
            body=msg
        ).execute()
        logger.info(
            f"Email sent to {to} | ID: {sent['id']}"
        )
        return {
            "message_id": sent["id"],
            "to": to,
            "subject": subject,
            "sent": True
        }

    return await asyncio.to_thread(_sync)


# ── Draft ──────────────────────────────────────────────

async def create_draft(
    to: str,
    subject: str,
    body: str,
    from_email: str
) -> dict:
    """Create a Gmail draft — non-blocking"""

    def _sync():
        service = _build_gmail_service_sync()
        msg = _build_message(to, subject, body, from_email)
        draft = service.users().drafts().create(
            userId="me",
            body={"message": msg}
        ).execute()
        logger.info(f"Draft created | ID: {draft['id']}")
        return {
            "draft_id": draft["id"],
            "to": to,
            "subject": subject,
            "gmail_drafts_url": (
                "https://mail.google.com/mail/u/0/#drafts"
            )
        }

    return await asyncio.to_thread(_sync)


async def delete_draft(draft_id: str) -> dict:
    """Delete a Gmail draft — non-blocking"""

    def _sync():
        service = _build_gmail_service_sync()
        service.users().drafts().delete(
            userId="me",
            id=draft_id
        ).execute()
        logger.info(f"Draft deleted: {draft_id}")
        return {"draft_id": draft_id, "deleted": True}

    return await asyncio.to_thread(_sync)


async def list_drafts(max_results: int = 10) -> List[dict]:
    """List Gmail drafts with details — non-blocking"""

    def _sync():
        service = _build_gmail_service_sync()
        result = service.users().drafts().list(
            userId="me",
            maxResults=max_results
        ).execute()

        drafts = result.get("drafts", [])
        detailed = []

        for draft in drafts:
            try:
                detail = service.users().drafts().get(
                    userId="me",
                    id=draft["id"]
                ).execute()

                headers = (
                    detail
                    .get("message", {})
                    .get("payload", {})
                    .get("headers", [])
                )

                subject = next(
                    (h["value"] for h in headers
                     if h["name"] == "Subject"),
                    "No subject"
                )
                to = next(
                    (h["value"] for h in headers
                     if h["name"] == "To"),
                    "Unknown"
                )

                detailed.append({
                    "draft_id": draft["id"],
                    "subject": subject,
                    "to": to
                })
            except Exception as e:
                logger.warning(
                    f"Could not fetch draft detail: {e}"
                )
                detailed.append({
                    "draft_id": draft["id"],
                    "subject": "Unknown",
                    "to": "Unknown"
                })

        return detailed

    return await asyncio.to_thread(_sync)