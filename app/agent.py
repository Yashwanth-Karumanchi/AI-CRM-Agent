import json
from app.logger import get_logger
from app.services.llm import generate_json, safe_str

logger = get_logger(__name__)


async def extract_client_from_pdf(pdf_text: str) -> dict:
    prompt = f"""Extract client info from this document.
Return ONLY valid JSON with these exact fields:
{{
    "name": "full name or empty string",
    "email": "email or empty string",
    "company": "company or empty string",
    "phone": "phone or empty string",
    "service": "service requested or empty string",
    "priority": "Low or Medium or High",
    "notes": "other relevant info",
    "executive_summary": "2-3 sentence summary",
    "business_problem": "main problem to solve",
    "current_process": "how they currently work",
    "recommendations": ["recommendation 1", "recommendation 2"],
    "open_questions": ["question 1", "question 2"]
}}

Document:
{pdf_text[:4000]}"""

    return await generate_json(prompt)


async def analyze_client(client: dict) -> dict:
    prompt = f"""Analyze this CRM client record.
Return ONLY valid JSON:
{{
    "executive_summary": "2-3 sentence overview",
    "business_problem": "their main challenge",
    "current_process": "how they currently work",
    "recommendations": ["action 1", "action 2", "action 3"],
    "open_questions": ["question 1", "question 2"],
    "next_actions": ["immediate action 1", "action 2"],
    "risk_level": "Low or Medium or High",
    "opportunity_score": "1-10",
    "notes": "additional insights"
}}

Client Record:
Name: {safe_str(client.get('name'))}
Company: {safe_str(client.get('company'))}
Email: {safe_str(client.get('email'))}
Service: {safe_str(client.get('service'))}
Priority: {safe_str(client.get('priority'))}
Stage: {safe_str(client.get('stage'))}
Notes: {safe_str(client.get('notes'))}
Created: {safe_str(client.get('created_at'))}"""

    return await generate_json(prompt)


async def draft_email(client: dict, instruction: str) -> dict:
    prompt = f"""Draft a professional email based on instructions.
Return ONLY valid JSON:
{{
    "subject": "clear professional subject line",
    "body": "complete email body text"
}}

Client:
Name: {safe_str(client.get('name'))}
Company: {safe_str(client.get('company', 'N/A'))}
Email: {safe_str(client.get('email', 'N/A'))}
Service: {safe_str(client.get('service', 'N/A'))}
Stage: {safe_str(client.get('stage'))}
Notes: {safe_str(client.get('notes', 'N/A'))}

Instructions: {instruction}"""

    result = await generate_json(prompt)
    return {
        "subject": result.get("subject", ""),
        "body": result.get("body", "")
    }


async def chat(
    message: str,
    client_id: str = None
) -> str:
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
        f"You are ARIA, an AI CRM assistant.\n"
        f"Answer professionally and concisely.\n"
        f"{context}\n\n"
        f"User: {message}\n\n"
        f"ARIA:"
    )

    from app.services.llm import generate
    return await generate(prompt)


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