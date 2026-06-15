import os
import base64
import json
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
    "https://www.googleapis.com/auth/gmail.drafts"
]

def get_gmail_service():
    """Get authenticated Gmail service using OAuth"""
    creds = None

    # Load existing token
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file(
            "token.json",
            SCOPES
        )

    # Refresh or get new token
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "gmail_oauth.json",
                SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Save token for next time
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)

def build_message(
    to: str,
    subject: str,
    body: str,
    from_email: str
) -> dict:
    """Build a Gmail message"""
    message = MIMEMultipart("alternative")
    message["to"] = to
    message["from"] = from_email
    message["subject"] = subject

    # Plain text part
    text_part = MIMEText(body, "plain")
    message.attach(text_part)

    # HTML part
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
    try:
        service = get_gmail_service()
        message = build_message(to, subject, body, from_email)

        sent = service.users().messages().send(
            userId="me",
            body=message
        ).execute()

        logger.info(f"Email sent to {to} | ID: {sent['id']}")

        return {
            "ok": True,
            "message_id": sent["id"],
            "to": to,
            "subject": subject
        }
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        raise ValueError(f"Failed to send email: {str(e)}")

async def create_draft(
    to: str,
    subject: str,
    body: str,
    from_email: str
) -> dict:
    """Create a Gmail draft"""
    try:
        service = get_gmail_service()
        message = build_message(to, subject, body, from_email)

        draft = service.users().drafts().create(
            userId="me",
            body={"message": message}
        ).execute()

        logger.info(f"Draft created for {to} | ID: {draft['id']}")

        return {
            "ok": True,
            "draft_id": draft["id"],
            "to": to,
            "subject": subject,
            "gmail_drafts_url": "https://mail.google.com/mail/u/0/#drafts"
        }
    except Exception as e:
        logger.error(f"Failed to create draft: {e}")
        raise ValueError(f"Failed to create draft: {str(e)}")