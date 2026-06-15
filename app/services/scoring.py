import json
from typing import List, Optional
from app.logger import get_logger

logger = get_logger(__name__)

async def score_client(client: dict, model) -> dict:
    """AI scores a client on multiple dimensions"""

    prompt = f"""
    Analyze this CRM client and provide scores and recommendations.
    Return ONLY a valid JSON object with these exact fields:

    {{
        "lead_score": <integer 1-10>,
        "lead_score_reason": "<why this score>",
        "churn_risk": "<Low|Medium|High>",
        "churn_risk_reason": "<why this risk level>",
        "sentiment": "<Positive|Neutral|Negative>",
        "sentiment_reason": "<based on notes and stage>",
        "opportunity_value": "<Low|Medium|High>",
        "best_next_action": "<single most important action>",
        "recommended_actions": [
            "<action 1>",
            "<action 2>",
            "<action 3>"
        ],
        "talking_points": [
            "<point 1>",
            "<point 2>"
        ],
        "estimated_close_probability": <integer 0-100>,
        "suggested_stage": "<New|Contacted|Consultation Scheduled|Proposal Sent|Won|Lost>",
        "stage_change_reason": "<why suggest this stage>",
        "summary": "<2-3 sentence overall assessment>"
    }}

    Client Data:
    Name: {client.get('name')}
    Company: {client.get('company', 'N/A')}
    Email: {client.get('email', 'N/A')}
    Service: {client.get('service', 'N/A')}
    Priority: {client.get('priority', 'Medium')}
    Stage: {client.get('stage', 'New')}
    Notes: {client.get('notes', 'None')}
    Next Follow-up: {client.get('next_follow_up', 'Not set')}
    Created: {client.get('created_at', 'Unknown')}

    Return only valid JSON. No explanation. No markdown.
    """

    response = model.models.generate_content(
        model="models/gemini-2.5-flash",
        contents=prompt
    )

    text = response.text.strip()
    text = text.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.error(f"Failed to parse scoring response: {text}")
        raise ValueError("AI could not score client")

async def score_pipeline(clients: List[dict], model) -> dict:
    """Score all clients and provide pipeline insights"""

    client_summaries = [
        {
            "client_id": c.get("client_id"),
            "name": c.get("name"),
            "company": c.get("company"),
            "stage": c.get("stage"),
            "priority": c.get("priority"),
            "service": c.get("service"),
            "notes": c.get("notes", "")[:200]
        }
        for c in clients
    ]

    prompt = f"""
    Analyze this entire CRM pipeline and provide insights.
    Return ONLY a valid JSON object with these exact fields:

    {{
        "pipeline_health": "<Excellent|Good|Fair|Poor>",
        "pipeline_health_reason": "<why>",
        "total_opportunity_value": "<Low|Medium|High>",
        "highest_priority_clients": [
            {{
                "client_id": "<id>",
                "name": "<name>",
                "reason": "<why highest priority>"
            }}
        ],
        "at_risk_clients": [
            {{
                "client_id": "<id>",
                "name": "<name>",
                "risk": "<what risk>"
            }}
        ],
        "stalled_clients": [
            {{
                "client_id": "<id>",
                "name": "<name>",
                "reason": "<why stalled>"
            }}
        ],
        "recommended_focus": "<what to focus on this week>",
        "pipeline_recommendations": [
            "<recommendation 1>",
            "<recommendation 2>",
            "<recommendation 3>"
        ],
        "win_probability_summary": "<overall win probability assessment>",
        "summary": "<3-4 sentence pipeline assessment>"
    }}

    Pipeline Data:
    Total Clients: {len(clients)}
    {json.dumps(client_summaries, indent=2)}

    Return only valid JSON. No explanation. No markdown.
    """

    response = model.models.generate_content(
        model="models/gemini-2.5-flash",
        contents=prompt
    )

    text = response.text.strip()
    text = text.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.error(f"Failed to parse pipeline scoring: {text}")
        raise ValueError("AI could not score pipeline")

async def detect_similar_clients(
    target_client: dict,
    all_clients: List[dict],
    model
) -> dict:
    """Find clients similar to a target client"""

    other_clients = [
        c for c in all_clients
        if c.get("client_id") != target_client.get("client_id")
    ]

    prompt = f"""
    Find clients most similar to the target client.
    Return ONLY a valid JSON object with these exact fields:

    {{
        "similar_clients": [
            {{
                "client_id": "<id>",
                "name": "<name>",
                "similarity_reason": "<why similar>",
                "similarity_score": <integer 1-10>
            }}
        ],
        "common_patterns": [
            "<pattern 1>",
            "<pattern 2>"
        ],
        "recommendation": "<what to do based on similar clients>"
    }}

    Target Client:
    {json.dumps(target_client, indent=2)}

    All Other Clients:
    {json.dumps([
        {{
            "client_id": c.get("client_id"),
            "name": c.get("name"),
            "company": c.get("company"),
            "service": c.get("service"),
            "stage": c.get("stage"),
            "priority": c.get("priority")
        }}
        for c in other_clients[:20]
    ], indent=2)}

    Return only valid JSON. No explanation. No markdown.
    """

    response = model.models.generate_content(
        model="models/gemini-2.5-flash",
        contents=prompt
    )

    text = response.text.strip()
    text = text.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        raise ValueError("AI could not find similar clients")

async def get_follow_up_recommendations(
    clients: List[dict],
    model
) -> dict:
    """AI recommends which clients to follow up with today"""

    from datetime import date
    today = date.today().isoformat()

    prompt = f"""
    Today is {today}.
    Analyze these clients and recommend follow-up priority.
    Return ONLY a valid JSON object with these exact fields:

    {{
        "immediate_followup": [
            {{
                "client_id": "<id>",
                "name": "<name>",
                "reason": "<why immediate>",
                "suggested_action": "<what to do>"
            }}
        ],
        "followup_this_week": [
            {{
                "client_id": "<id>",
                "name": "<name>",
                "reason": "<why this week>",
                "suggested_action": "<what to do>"
            }}
        ],
        "can_wait": [
            {{
                "client_id": "<id>",
                "name": "<name>",
                "reason": "<why can wait>"
            }}
        ],
        "daily_plan": "<2-3 sentence plan for today>"
    }}

    Clients:
    {json.dumps([
        {{
            "client_id": c.get("client_id"),
            "name": c.get("name"),
            "company": c.get("company"),
            "stage": c.get("stage"),
            "priority": c.get("priority"),
            "next_follow_up": c.get("next_follow_up", "Not set"),
            "notes": c.get("notes", "")[:100]
        }}
        for c in clients[:30]
    ], indent=2)}

    Return only valid JSON. No explanation. No markdown.
    """

    response = model.models.generate_content(
        model="models/gemini-2.5-flash",
        contents=prompt
    )

    text = response.text.strip()
    text = text.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        raise ValueError("AI could not generate recommendations")