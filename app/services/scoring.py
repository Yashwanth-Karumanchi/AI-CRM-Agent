import json
from typing import List
from app.logger import get_logger
from app.services.llm import generate_json, safe_str

logger = get_logger(__name__)

# Max clients to analyze in pipeline scoring
MAX_PIPELINE_CLIENTS = 50
MAX_FOLLOWUP_CLIENTS = 30


async def score_client(client: dict) -> dict:
    """
    Score a single client on multiple dimensions.
    Returns structured scoring with actionable insights.
    """
    prompt = f"""You are a CRM analyst. Score this client.
Return ONLY valid JSON — no text before or after:
{{
    "lead_score": 7,
    "lead_score_reason": "1-2 sentence explanation",
    "churn_risk": "Low",
    "churn_risk_reason": "1-2 sentence explanation",
    "sentiment": "Positive",
    "sentiment_reason": "based on notes and stage",
    "opportunity_value": "High",
    "best_next_action": "single most important action right now",
    "recommended_actions": [
        "specific action 1",
        "specific action 2",
        "specific action 3"
    ],
    "talking_points": [
        "key talking point 1",
        "key talking point 2"
    ],
    "estimated_close_probability": 70,
    "suggested_stage": "Consultation Scheduled",
    "stage_change_reason": "why suggest this stage",
    "summary": "2-3 sentence overall assessment"
}}

Scoring criteria:
- lead_score: 1-10 (10 = highest quality lead)
- churn_risk: Low / Medium / High
- sentiment: Positive / Neutral / Negative
- opportunity_value: Low / Medium / High
- estimated_close_probability: 0-100 integer

Client Data:
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


async def score_pipeline(clients: List[dict]) -> dict:
    """
    Analyze overall pipeline health.
    Caps at MAX_PIPELINE_CLIENTS to avoid token limits.
    """
    # Sort by priority for most relevant analysis
    priority_order = {"High": 0, "Medium": 1, "Low": 2}
    sorted_clients = sorted(
        clients,
        key=lambda c: priority_order.get(
            c.get("priority", "Low"), 2
        )
    )[:MAX_PIPELINE_CLIENTS]

    summaries = [
        {
            "client_id": safe_str(c.get("client_id")),
            "name": safe_str(c.get("name")),
            "company": safe_str(c.get("company")),
            "stage": safe_str(c.get("stage")),
            "priority": safe_str(c.get("priority")),
            "service": safe_str(c.get("service")),
            "notes": safe_str(c.get("notes"))[:80]
        }
        for c in sorted_clients
    ]

    prompt = f"""You are a CRM analyst. Assess pipeline health.
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
            "risk": "specific risk description"
        }}
    ],
    "stalled_clients": [
        {{
            "client_id": "CL-XXXX",
            "name": "name",
            "reason": "why stalled"
        }}
    ],
    "recommended_focus": "1-2 sentence focus for this week",
    "pipeline_recommendations": [
        "specific recommendation 1",
        "specific recommendation 2",
        "specific recommendation 3"
    ],
    "win_probability_summary": "overall win probability",
    "summary": "3-4 sentence pipeline assessment"
}}

Values for pipeline_health: Excellent / Good / Fair / Poor
Values for total_opportunity_value: Low / Medium / High

Total Clients Analyzed: {len(sorted_clients)}
Client Data:
{json.dumps(summaries, indent=2)}"""

    return await generate_json(prompt)


async def detect_similar_clients(
    target_client: dict,
    all_clients: List[dict]
) -> dict:
    """Find clients similar to a target client"""
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
        if c.get("client_id") != \
           target_client.get("client_id")
    ][:25]  # Cap at 25 for token safety

    prompt = f"""Find the most similar CRM clients to the target.
Return ONLY valid JSON:
{{
    "similar_clients": [
        {{
            "client_id": "CL-XXXX",
            "name": "name",
            "similarity_reason": "specific reason",
            "similarity_score": 8
        }}
    ],
    "common_patterns": [
        "pattern 1",
        "pattern 2"
    ],
    "recommendation": "specific actionable recommendation"
}}

similarity_score: 1-10 (10 = most similar)
Return top 5 most similar clients only.

Target Client:
Name: {safe_str(target_client.get('name'))}
Company: {safe_str(target_client.get('company'))}
Service: {safe_str(target_client.get('service'))}
Stage: {safe_str(target_client.get('stage'))}
Priority: {safe_str(target_client.get('priority'))}
Notes: {safe_str(target_client.get('notes'))[:100]}

Comparison Pool ({len(others)} clients):
{json.dumps(others, indent=2)}"""

    return await generate_json(prompt)


async def get_follow_up_recommendations(
    clients: List[dict]
) -> dict:
    """
    Recommend who to contact today.
    Prioritises overdue follow-ups and high priority.
    """
    from datetime import date
    today = date.today().isoformat()

    # Sort: overdue first, then by priority
    def sort_key(c):
        fu = c.get("next_follow_up", "")
        overdue = fu and fu <= today
        pri = {"High": 0, "Medium": 1, "Low": 2}.get(
            c.get("priority", "Low"), 2
        )
        return (0 if overdue else 1, pri)

    sorted_clients = sorted(clients, key=sort_key)
    sample = sorted_clients[:MAX_FOLLOWUP_CLIENTS]

    client_data = [
        {
            "client_id": safe_str(c.get("client_id")),
            "name": safe_str(c.get("name")),
            "company": safe_str(c.get("company")),
            "stage": safe_str(c.get("stage")),
            "priority": safe_str(c.get("priority")),
            "next_follow_up": safe_str(
                c.get("next_follow_up")
            ),
            "notes": safe_str(c.get("notes"))[:80],
            "overdue": bool(
                c.get("next_follow_up") and
                c.get("next_follow_up") <= today
            )
        }
        for c in sample
    ]

    prompt = f"""Today is {today}. You are a CRM advisor.
Prioritize follow-ups for these clients.
Return ONLY valid JSON:
{{
    "immediate_followup": [
        {{
            "client_id": "CL-XXXX",
            "name": "name",
            "reason": "specific reason for urgency",
            "suggested_action": "exactly what to do"
        }}
    ],
    "followup_this_week": [
        {{
            "client_id": "CL-XXXX",
            "name": "name",
            "reason": "why this week",
            "suggested_action": "exactly what to do"
        }}
    ],
    "can_wait": [
        {{
            "client_id": "CL-XXXX",
            "name": "name",
            "reason": "why can wait"
        }}
    ],
    "daily_plan": "2-3 sentence specific action plan for today"
}}

immediate_followup = overdue or urgent
followup_this_week = due soon or high priority
can_wait = low priority, no urgency

Clients ({len(sample)} shown):
{json.dumps(client_data, indent=2)}"""

    return await generate_json(prompt)