import json
from typing import List
from app.logger import get_logger
from app.services.llm import generate_json, safe_str

logger = get_logger(__name__)


async def score_client(client: dict) -> dict:
    prompt = f"""Score this CRM client as a sales lead.
Return ONLY valid JSON:
{{
    "lead_score": 7,
    "lead_score_reason": "explanation",
    "churn_risk": "Low",
    "churn_risk_reason": "explanation",
    "sentiment": "Positive",
    "sentiment_reason": "explanation",
    "opportunity_value": "High",
    "best_next_action": "single most important action now",
    "recommended_actions": [
        "action 1",
        "action 2",
        "action 3"
    ],
    "talking_points": [
        "talking point 1",
        "talking point 2"
    ],
    "estimated_close_probability": 70,
    "suggested_stage": "Consultation Scheduled",
    "stage_change_reason": "explanation",
    "summary": "2-3 sentence overall assessment"
}}

Client:
Name: {safe_str(client.get('name'))}
Company: {safe_str(client.get('company'))}
Email: {safe_str(client.get('email'))}
Service: {safe_str(client.get('service'))}
Priority: {safe_str(client.get('priority'))}
Stage: {safe_str(client.get('stage'))}
Notes: {safe_str(client.get('notes'))}
Next Follow-up: {safe_str(client.get('next_follow_up'))}
Created: {safe_str(client.get('created_at'))}"""

    return await generate_json(prompt)


async def score_pipeline(clients: List[dict]) -> dict:
    summaries = [
        {
            "client_id": safe_str(c.get("client_id")),
            "name": safe_str(c.get("name")),
            "company": safe_str(c.get("company")),
            "stage": safe_str(c.get("stage")),
            "priority": safe_str(c.get("priority")),
            "service": safe_str(c.get("service")),
            "notes": safe_str(c.get("notes"))[:100]
        }
        for c in clients
    ]

    prompt = f"""Analyze this CRM pipeline health.
Return ONLY valid JSON:
{{
    "pipeline_health": "Good",
    "pipeline_health_reason": "explanation",
    "total_opportunity_value": "Medium",
    "highest_priority_clients": [
        {{
            "client_id": "CL-XXXX",
            "name": "name",
            "reason": "why highest priority"
        }}
    ],
    "at_risk_clients": [
        {{
            "client_id": "CL-XXXX",
            "name": "name",
            "risk": "what risk"
        }}
    ],
    "stalled_clients": [
        {{
            "client_id": "CL-XXXX",
            "name": "name",
            "reason": "why stalled"
        }}
    ],
    "recommended_focus": "what to focus on this week",
    "pipeline_recommendations": [
        "recommendation 1",
        "recommendation 2",
        "recommendation 3"
    ],
    "win_probability_summary": "overall win probability",
    "summary": "3-4 sentence pipeline assessment"
}}

Total Clients: {len(clients)}
Client Data:
{json.dumps(summaries, indent=2)}"""

    return await generate_json(prompt)


async def detect_similar_clients(
    target_client: dict,
    all_clients: List[dict]
) -> dict:
    others = [
        {
            "client_id": safe_str(c.get("client_id")),
            "name": safe_str(c.get("name")),
            "company": safe_str(c.get("company")),
            "service": safe_str(c.get("service")),
            "stage": safe_str(c.get("stage")),
            "priority": safe_str(c.get("priority"))
        }
        for c in all_clients
        if c.get("client_id") != target_client.get("client_id")
    ]

    prompt = f"""Find clients most similar to the target.
Return ONLY valid JSON:
{{
    "similar_clients": [
        {{
            "client_id": "CL-XXXX",
            "name": "name",
            "similarity_reason": "why similar",
            "similarity_score": 8
        }}
    ],
    "common_patterns": [
        "pattern 1",
        "pattern 2"
    ],
    "recommendation": "actionable recommendation"
}}

Target Client:
Name: {safe_str(target_client.get('name'))}
Company: {safe_str(target_client.get('company'))}
Service: {safe_str(target_client.get('service'))}
Stage: {safe_str(target_client.get('stage'))}
Priority: {safe_str(target_client.get('priority'))}

Other Clients:
{json.dumps(others[:20], indent=2)}"""

    return await generate_json(prompt)


async def get_follow_up_recommendations(
    clients: List[dict]
) -> dict:
    from datetime import date
    today = date.today().isoformat()

    client_data = [
        {
            "client_id": safe_str(c.get("client_id")),
            "name": safe_str(c.get("name")),
            "company": safe_str(c.get("company")),
            "stage": safe_str(c.get("stage")),
            "priority": safe_str(c.get("priority")),
            "next_follow_up": safe_str(c.get("next_follow_up")),
            "notes": safe_str(c.get("notes"))[:100]
        }
        for c in clients[:30]
    ]

    prompt = f"""Today is {today}.
Recommend follow-up priority for these CRM clients.
Return ONLY valid JSON:
{{
    "immediate_followup": [
        {{
            "client_id": "CL-XXXX",
            "name": "name",
            "reason": "why immediate",
            "suggested_action": "what to do"
        }}
    ],
    "followup_this_week": [
        {{
            "client_id": "CL-XXXX",
            "name": "name",
            "reason": "why this week",
            "suggested_action": "what to do"
        }}
    ],
    "can_wait": [
        {{
            "client_id": "CL-XXXX",
            "name": "name",
            "reason": "why can wait"
        }}
    ],
    "daily_plan": "2-3 sentence action plan for today"
}}

Clients:
{json.dumps(client_data, indent=2)}"""

    return await generate_json(prompt)