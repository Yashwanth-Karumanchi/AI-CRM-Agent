import json
from app.logger import get_logger
from app.services.llm import (
    generate_json,
    generate,
    generate_with_document,
    safe_str
)

logger = get_logger(__name__)


async def extract_client_from_pdf(pdf_text: str) -> dict:
    """
    Extract structured client data from PDF text.
    Used by /process-pdf and ARIA chat file uploads.
    """
    prompt = f"""Extract client information from this document.
Return ONLY valid JSON with these exact fields:
{{
    "name": "full name or empty string",
    "email": "email or empty string",
    "company": "company name or empty string",
    "phone": "phone number or empty string",
    "service": "service requested or empty string",
    "priority": "Low or Medium or High",
    "notes": "other relevant info",
    "executive_summary": "2-3 sentence summary",
    "business_problem": "main problem they need solved",
    "current_process": "how they currently work",
    "recommendations": [
        "recommendation 1",
        "recommendation 2"
    ],
    "open_questions": [
        "question 1",
        "question 2"
    ]
}}

Rules:
- Use empty string "" if info not found
- priority: default to Medium if unclear
- Extract name from signature, letterhead, or intro

Document:
{pdf_text[:4000]}"""

    return await generate_json(prompt)


async def analyze_client(client: dict) -> dict:
    """
    Deep AI analysis of a single client record.
    Used for reports, proposals, and ARIA chat.
    """
    prompt = f"""Analyze this CRM client record thoroughly.
Return ONLY valid JSON:
{{
    "executive_summary": "2-3 sentence overview of this client",
    "business_problem": "their main challenge or need",
    "current_process": "how they currently work",
    "recommendations": [
        "specific action 1",
        "specific action 2",
        "specific action 3"
    ],
    "open_questions": [
        "question to clarify 1",
        "question to clarify 2"
    ],
    "next_actions": [
        "immediate action to take 1",
        "immediate action to take 2"
    ],
    "risk_level": "Low or Medium or High",
    "opportunity_score": "1-10",
    "notes": "additional insights or observations"
}}

Client Record:
Name: {safe_str(client.get('name'))}
Company: {safe_str(client.get('company'))}
Email: {safe_str(client.get('email'))}
Phone: {safe_str(client.get('phone'))}
Service: {safe_str(client.get('service'))}
Priority: {safe_str(client.get('priority'))}
Stage: {safe_str(client.get('stage'))}
Notes: {safe_str(client.get('notes'))}
Next Follow-up: {safe_str(client.get('next_follow_up'))}
Created: {safe_str(client.get('created_at'))}"""

    return await generate_json(prompt)


async def analyze_document_content(
    document_text: str,
    user_question: str,
    file_type: str = "document"
) -> str:
    """
    Answer a user's question about an uploaded document.
    Used by ARIA chat file upload handler.
    """
    prompt = (
        f"You are ARIA, an AI CRM assistant. "
        f"A user uploaded a {file_type} and asked: "
        f'"{user_question}"\n\n'
        f"Analyze the document and give a helpful, "
        f"specific answer. If relevant to CRM (client info, "
        f"contact details, services needed), highlight that.\n\n"
        f"Be concise and actionable."
    )
    return await generate_with_document(
        prompt, document_text, max_doc_chars=6000
    )


async def draft_email(
    client: dict,
    instruction: str
) -> dict:
    """
    Draft a professional email for a client.
    Returns {subject, body}.
    """
    prompt = f"""Draft a professional email based on the instruction below.
Return ONLY valid JSON:
{{
    "subject": "clear, professional subject line",
    "body": "complete email body — professional but warm tone"
}}

Rules:
- Address the client by first name
- Keep body under 300 words unless instruction says otherwise
- No placeholders like [NAME] — use actual client data
- Sign off with: Best regards, Yashwanth Karumanchi, yashwanthkarumanchi@gmail.com.

Client:
Name: {safe_str(client.get('name'))}
Company: {safe_str(client.get('company', 'N/A'))}
Email: {safe_str(client.get('email', 'N/A'))}
Service: {safe_str(client.get('service', 'N/A'))}
Stage: {safe_str(client.get('stage'))}
Notes: {safe_str(client.get('notes', 'N/A'))}
Next Follow-up: {safe_str(client.get('next_follow_up', 'N/A'))}

Instructions: {instruction}"""

    result = await generate_json(prompt)
    return {
        "subject": str(result.get("subject", "Follow Up")),
        "body":    str(result.get("body", ""))
    }


async def chat(
    message: str,
    client_id: str = None
) -> str:
    """
    Simple AI chat with CRM context.
    Used by /agent/chat endpoint.
    """
    from app.services import sheets

    context = ""
    if client_id:
        try:
            client = await sheets.get_client_by_id(client_id)
            if client:
                context = (
                    f"\nClient Context:\n"
                    f"Name: {safe_str(client.get('name'))}\n"
                    f"Company: {safe_str(client.get('company'))}\n"
                    f"Stage: {safe_str(client.get('stage'))}\n"
                    f"Priority: {safe_str(client.get('priority'))}\n"
                    f"Service: {safe_str(client.get('service'))}\n"
                    f"Notes: {safe_str(client.get('notes'))}\n"
                )
        except Exception:
            pass
    else:
        try:
            summary = await sheets.get_pipeline_summary()
            context = (
                f"\nPipeline Summary:\n"
                f"Total Clients: "
                f"{summary.get('total_clients', 0)}\n"
                f"High Priority: "
                f"{summary.get('high_priority_pending_count', 0)}\n"
                f"Won: {summary.get('won_count', 0)}\n"
                f"Stages: "
                f"{json.dumps(summary.get('stage_counts', {}))}\n"
            )
        except Exception:
            pass

    prompt = (
        f"You are ARIA, an AI CRM assistant. "
        f"Answer professionally and concisely.\n"
        f"{context}\n\n"
        f"User: {message}\n\n"
        f"ARIA:"
    )

    return await generate(prompt)


# ── Scoring ────────────────────────────────────────────

async def score_single_client(client: dict) -> dict:
    from app.services.scoring import score_client
    return await score_client(client)


async def score_entire_pipeline(clients: list) -> dict:
    from app.services.scoring import score_pipeline
    return await score_pipeline(clients)


async def find_similar_clients(
    target_client: dict,
    all_clients: list
) -> dict:
    from app.services.scoring import detect_similar_clients
    return await detect_similar_clients(
        target_client, all_clients
    )


async def get_daily_recommendations(clients: list) -> dict:
    from app.services.scoring import (
        get_follow_up_recommendations
    )
    return await get_follow_up_recommendations(clients)


# ── Search / Intelligence ──────────────────────────────

async def nl_search(query: str, clients: list) -> dict:
    from app.services.search import natural_language_search
    return await natural_language_search(query, clients)


async def pipeline_patterns(clients: list) -> dict:
    from app.services.search import detect_patterns
    return await detect_patterns(clients)


async def smart_filter(criteria: str, clients: list) -> dict:
    from app.services.search import intelligent_filter
    return await intelligent_filter(criteria, clients)


async def forecast_revenue(clients: list) -> dict:
    from app.services.search import revenue_forecast
    return await revenue_forecast(clients)


async def analyze_win_loss(clients: list) -> dict:
    from app.services.search import win_loss_analysis
    return await win_loss_analysis(clients)