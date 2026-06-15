import os
import json
from datetime import datetime, timedelta
from typing import Optional, List
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from app.logger import get_logger

logger = get_logger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events"
]

def get_calendar_service():
    """Get authenticated Google Calendar service"""
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
            logger.error(f"Failed to load token: {e}")

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
        raise ValueError(
            "No valid Calendar credentials. "
            "Set GMAIL_TOKEN environment variable."
        )

    return build("calendar", "v3", credentials=creds)

async def schedule_meeting(
    client: dict,
    title: str,
    start_time: str,
    end_time: str,
    description: Optional[str] = None,
    location: Optional[str] = None,
    invite_client: bool = False,
    meeting_notes: Optional[str] = None
) -> dict:
    """Schedule a meeting with a client"""
    service = get_calendar_service()

    event_description = description or (
        f"Client ID: {client['client_id']}\n"
        f"Company: {client.get('company', 'N/A')}\n"
        f"Service: {client.get('service', 'N/A')}\n"
        f"Stage: {client.get('stage', 'N/A')}"
    )

    if meeting_notes:
        event_description += f"\n\nNotes:\n{meeting_notes}"

    event = {
        "summary": title or f"Meeting - {client.get('company') or client['name']}",
        "description": event_description,
        "start": {
            "dateTime": start_time,
            "timeZone": "America/Denver"
        },
        "end": {
            "dateTime": end_time,
            "timeZone": "America/Denver"
        },
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "email", "minutes": 24 * 60},
                {"method": "popup", "minutes": 30}
            ]
        }
    }

    if location:
        event["location"] = location

    if invite_client and client.get("email"):
        event["attendees"] = [
            {"email": client["email"]}
        ]
        event["guestsCanSeeOtherGuests"] = False

    created = service.events().insert(
        calendarId="primary",
        body=event,
        sendUpdates="all" if invite_client else "none"
    ).execute()

    logger.info(f"Meeting scheduled: {created['id']}")

    return {
        "event_id": created["id"],
        "title": created["summary"],
        "start_time": created["start"]["dateTime"],
        "end_time": created["end"]["dateTime"],
        "calendar_link": created.get("htmlLink"),
        "meet_link": created.get("hangoutLink"),
        "invited_client": invite_client
    }

async def get_upcoming_meetings(
    days_ahead: int = 7,
    max_results: int = 10
) -> List[dict]:
    """Get upcoming meetings from Google Calendar"""
    service = get_calendar_service()

    now = datetime.utcnow().isoformat() + "Z"
    future = (
        datetime.utcnow() + timedelta(days=days_ahead)
    ).isoformat() + "Z"

    events_result = service.events().list(
        calendarId="primary",
        timeMin=now,
        timeMax=future,
        maxResults=max_results,
        singleEvents=True,
        orderBy="startTime"
    ).execute()

    events = events_result.get("items", [])

    return [
        {
            "event_id": e["id"],
            "title": e.get("summary", "No title"),
            "start_time": e["start"].get(
                "dateTime", e["start"].get("date")
            ),
            "end_time": e["end"].get(
                "dateTime", e["end"].get("date")
            ),
            "description": e.get("description", ""),
            "location": e.get("location", ""),
            "attendees": [
                a["email"]
                for a in e.get("attendees", [])
            ],
            "meet_link": e.get("hangoutLink", ""),
            "calendar_link": e.get("htmlLink", "")
        }
        for e in events
    ]

async def get_meeting(event_id: str) -> dict:
    """Get a specific calendar event"""
    service = get_calendar_service()

    event = service.events().get(
        calendarId="primary",
        eventId=event_id
    ).execute()

    return {
        "event_id": event["id"],
        "title": event.get("summary", "No title"),
        "start_time": event["start"].get(
            "dateTime", event["start"].get("date")
        ),
        "end_time": event["end"].get(
            "dateTime", event["end"].get("date")
        ),
        "description": event.get("description", ""),
        "location": event.get("location", ""),
        "attendees": [
            a["email"]
            for a in event.get("attendees", [])
        ],
        "meet_link": event.get("hangoutLink", ""),
        "calendar_link": event.get("htmlLink", ""),
        "status": event.get("status", "confirmed")
    }

async def update_meeting(
    event_id: str,
    title: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    description: Optional[str] = None,
    location: Optional[str] = None,
    meeting_notes: Optional[str] = None
) -> dict:
    """Update an existing calendar event"""
    service = get_calendar_service()

    event = service.events().get(
        calendarId="primary",
        eventId=event_id
    ).execute()

    if title:
        event["summary"] = title
    if start_time:
        event["start"]["dateTime"] = start_time
    if end_time:
        event["end"]["dateTime"] = end_time
    if location:
        event["location"] = location
    if description:
        event["description"] = description
    if meeting_notes:
        existing_desc = event.get("description", "")
        event["description"] = (
            existing_desc +
            f"\n\nUpdated Notes:\n{meeting_notes}"
        )

    updated = service.events().update(
        calendarId="primary",
        eventId=event_id,
        body=event,
        sendUpdates="all"
    ).execute()

    logger.info(f"Meeting updated: {event_id}")

    return {
        "event_id": updated["id"],
        "title": updated["summary"],
        "start_time": updated["start"]["dateTime"],
        "end_time": updated["end"]["dateTime"],
        "calendar_link": updated.get("htmlLink"),
        "updated": True
    }

async def cancel_meeting(
    event_id: str,
    notify_attendees: bool = True
) -> dict:
    """Cancel a calendar event"""
    service = get_calendar_service()

    service.events().delete(
        calendarId="primary",
        eventId=event_id,
        sendUpdates="all" if notify_attendees else "none"
    ).execute()

    logger.info(f"Meeting cancelled: {event_id}")

    return {
        "event_id": event_id,
        "cancelled": True,
        "attendees_notified": notify_attendees
    }

async def add_meeting_notes(
    event_id: str,
    notes: str
) -> dict:
    """Add notes to an existing calendar event"""
    service = get_calendar_service()

    event = service.events().get(
        calendarId="primary",
        eventId=event_id
    ).execute()

    existing_desc = event.get("description", "")
    timestamp = datetime.utcnow().strftime(
        "%Y-%m-%d %H:%M UTC"
    )

    event["description"] = (
        existing_desc +
        f"\n\n--- Notes added {timestamp} ---\n{notes}"
    )

    updated = service.events().update(
        calendarId="primary",
        eventId=event_id,
        body=event
    ).execute()

    logger.info(f"Notes added to meeting: {event_id}")

    return {
        "event_id": event_id,
        "notes_added": True,
        "timestamp": timestamp
    }

async def get_client_meetings(
    client_email: str,
    days_back: int = 30,
    days_ahead: int = 30
) -> List[dict]:
    """Get all meetings involving a specific client"""
    service = get_calendar_service()

    past = (
        datetime.utcnow() - timedelta(days=days_back)
    ).isoformat() + "Z"

    future = (
        datetime.utcnow() + timedelta(days=days_ahead)
    ).isoformat() + "Z"

    events_result = service.events().list(
        calendarId="primary",
        timeMin=past,
        timeMax=future,
        maxResults=50,
        singleEvents=True,
        orderBy="startTime"
    ).execute()

    events = events_result.get("items", [])

    client_meetings = []
    for e in events:
        attendees = [
            a["email"]
            for a in e.get("attendees", [])
        ]
        if client_email in attendees:
            client_meetings.append({
                "event_id": e["id"],
                "title": e.get("summary", "No title"),
                "start_time": e["start"].get(
                    "dateTime", e["start"].get("date")
                ),
                "end_time": e["end"].get(
                    "dateTime", e["end"].get("date")
                ),
                "status": e.get("status", "confirmed"),
                "meet_link": e.get("hangoutLink", ""),
                "calendar_link": e.get("htmlLink", "")
            })

    return client_meetings