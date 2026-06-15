import os
import base64
import json
from typing import List
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
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

def get_gmail_service():
    """Get authenticated Gmail service"""
    creds = None

    token_env = os.getenv("GMAIL_TOKEN")
    if token_env:
        try:
            token_data = json.loads(token_env)
            creds = Credentials(
                token=token_data.get("token"),
                refresh_token=token_data.get("refresh_token"),
                token_uri=token_data.get("token_uri",
                    "https://oauth2.googleapis.com/token"),
                client_id=token_data.get("client_id"),
                client_secret=token_data.get("client_secret"),
                scopes=token_data.get("scopes", SCOPES)
            )
        except Exception as e:
            logger.error(f"Failed to load GMAIL_TOKEN: {e}")

    elif os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file(
            "token.json", SCOPES
        )

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception as e:
            raise ValueError(f"Token refresh failed: {e}")

    if not creds or not creds.valid:
        if os.path.exists("gmail_oauth.json"):
            flow = InstalledAppFlow.from_client_secrets_file(
                "gmail_oauth.json", SCOPES
            )
            creds = flow.run_local_server(
                port=0,
                access_type="offline",
                prompt="consent"
            )
            with open("token.json", "w") as f:
                f.write(creds.to_json())
        else:
            raise ValueError(
                "No Gmail credentials. "
                "Set GMAIL_TOKEN environment variable."
            )

    return build("gmail", "v1", credentials=creds)

def build_message(
    to: str,
    subject: str,
    body: str,
    from_email: str
) -> dict:
    message = MIMEMultipart("alternative")
    message["to"] = to
    message["from"] = from_email
    message["subject"] = subject

    text_part = MIMEText(body, "plain")
    message.attach(text_part)

    html_body = body.replace("\n", "<br>")
    html_part = MIMEText(
        f"<html><body><p>{html_body}</p></body></html>",
        "html"
    )
    message.attach(html_part)

    raw = base64.urlsafe_b64encode(
        message.as_bytes()
    ).decode("utf-8")

    return {"raw": raw}

async def send_email(
    to: str,
    subject: str,
    body: str,
    from_email: str
) -> dict:
    """Send a real email via Gmail"""
    service = get_gmail_service()
    message = build_message(to, subject, body, from_email)

    sent = service.users().messages().send(
        userId="me",
        body=message
    ).execute()

    logger.info(f"Email sent to {to} | ID: {sent['id']}")

    return {
        "message_id": sent["id"],
        "to": to,
        "subject": subject,
        "sent": True
    }

async def create_draft(
    to: str,
    subject: str,
    body: str,
    from_email: str
) -> dict:
    """Create a Gmail draft"""
    service = get_gmail_service()
    message = build_message(to, subject, body, from_email)

    draft = service.users().drafts().create(
        userId="me",
        body={"message": message}
    ).execute()

    logger.info(f"Draft created | ID: {draft['id']}")

    return {
        "draft_id": draft["id"],
        "to": to,
        "subject": subject,
        "gmail_drafts_url": "https://mail.google.com/mail/u/0/#drafts"
    }

async def delete_draft(draft_id: str) -> dict:
    """Delete a Gmail draft"""
    service = get_gmail_service()

    service.users().drafts().delete(
        userId="me",
        id=draft_id
    ).execute()

    logger.info(f"Draft deleted: {draft_id}")

    return {
        "draft_id": draft_id,
        "deleted": True
    }

async def list_drafts(max_results: int = 10) -> List[dict]:
    """List Gmail drafts"""
    service = get_gmail_service()

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

            headers = detail.get("message", {}).get(
                "payload", {}
            ).get("headers", [])

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
        except Exception:
            detailed.append({"draft_id": draft["id"]})

    return detailed