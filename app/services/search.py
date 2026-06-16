import json
from typing import List
from app.logger import get_logger
from app.services.llm import generate_json, safe_str

logger = get_logger(__name__)


def _client_summary(c: dict) -> dict:
    return {
        "client_id": safe_str(c.get("client_id")),
        "name": safe_str(c.get("name")),
        "company": safe_str(c.get("company")),
        "email": safe_str(c.get("email")),
        "service": safe_str(c.get("service")),
        "priority": safe_str(c.get("priority")),
        "stage": safe_str(c.get("stage")),
        "notes": safe_str(c.get("notes"))[:150],
        "next_follow_up": safe_str(c.get("next_follow_up")),
        "created_at": safe_str(c.get("created_at"))
    }


async def natural_language_search(
    query: str,
    clients: List[dict]
) -> dict:
    prompt = f"""Search CRM clients matching this query: "{query}"

Return ONLY valid JSON:
{{
    "matching_client_ids": ["CL-XXXX", "CL-YYYY"],
    "search_interpretation": "how you interpreted the query",
    "filters_applied": ["filter 1", "filter 2"],
    "total_matches": 2,
    "confidence": "High",
    "suggestion": "alternative search if no matches"
}}

Available Clients:
{json.dumps([_client_summary(c) for c in clients], indent=2)}"""

    result = await generate_json(prompt)
    matching_ids = result.get("matching_client_ids", [])
    result["matched_clients"] = [
        c for c in clients
        if c.get("client_id") in matching_ids
    ]
    return result


async def detect_patterns(clients: List[dict]) -> dict:
    prompt = f"""Detect patterns across these CRM clients.
Return ONLY valid JSON:
{{
    "total_analyzed": {len(clients)},
    "segments": [
        {{
            "segment_name": "segment name",
            "description": "what defines this segment",
            "client_ids": ["CL-XXXX"],
            "size": 1,
            "opportunity": "High"
        }}
    ],
    "common_services": [
        {{
            "service": "service name",
            "count": 1,
            "win_rate": "50%"
        }}
    ],
    "stage_bottlenecks": [
        {{
            "stage": "stage name",
            "issue": "what the bottleneck is",
            "recommendation": "how to fix"
        }}
    ],
    "priority_distribution": {{
        "High": 0,
        "Medium": 0,
        "Low": 0
    }},
    "key_insights": [
        "insight 1",
        "insight 2",
        "insight 3"
    ],
    "growth_opportunities": [
        "opportunity 1",
        "opportunity 2"
    ],
    "risks": [
        "risk 1",
        "risk 2"
    ],
    "summary": "3-4 sentence analysis of the pipeline"
}}

Client Data ({len(clients)} clients):
{json.dumps([_client_summary(c) for c in clients], indent=2)}"""

    return await generate_json(prompt)


async def intelligent_filter(
    criteria: str,
    clients: List[dict]
) -> dict:
    from datetime import date
    today = date.today().isoformat()

    prompt = f"""Today is {today}.
Filter CRM clients matching: "{criteria}"

Return ONLY valid JSON:
{{
    "matching_client_ids": ["CL-XXXX"],
    "criteria_interpretation": "how you interpreted the criteria",
    "total_matches": 1,
    "reasoning": "why these clients match",
    "suggested_action": "what to do with these clients"
}}

Clients:
{json.dumps([_client_summary(c) for c in clients], indent=2)}"""

    result = await generate_json(prompt)
    matching_ids = result.get("matching_client_ids", [])
    result["matched_clients"] = [
        c for c in clients
        if c.get("client_id") in matching_ids
    ]
    return result


async def revenue_forecast(clients: List[dict]) -> dict:
    prompt = f"""Forecast revenue from this CRM pipeline.
Return ONLY valid JSON:
{{
    "total_pipeline_value": "estimated range",
    "expected_revenue_30_days": "30 day estimate",
    "expected_revenue_90_days": "90 day estimate",
    "confidence_level": "Medium",
    "high_confidence_deals": [
        {{
            "client_id": "CL-XXXX",
            "name": "name",
            "estimated_value": "$X,000",
            "close_probability": 80,
            "expected_close_date": "2026-07-01"
        }}
    ],
    "at_risk_revenue": "estimated at risk",
    "recommendations": [
        "action to increase revenue 1",
        "action to increase revenue 2"
    ],
    "assumptions": [
        "assumption 1",
        "assumption 2"
    ],
    "summary": "3-4 sentence forecast summary"
}}

Pipeline ({len(clients)} clients):
{json.dumps([_client_summary(c) for c in clients], indent=2)}"""

    return await generate_json(prompt)


async def win_loss_analysis(clients: List[dict]) -> dict:
    won = [
        c for c in clients
        if c.get("stage") == "Won"
    ]
    lost = [
        c for c in clients
        if c.get("stage") == "Lost"
    ]

    prompt = f"""Analyze won and lost CRM deals for patterns.
Return ONLY valid JSON:
{{
    "total_won": {len(won)},
    "total_lost": {len(lost)},
    "win_rate": "{round(len(won)/(len(won)+len(lost))*100) if (len(won)+len(lost)) > 0 else 0}%",
    "winning_patterns": [
        "pattern in won deals 1",
        "pattern in won deals 2"
    ],
    "losing_patterns": [
        "pattern in lost deals 1",
        "pattern in lost deals 2"
    ],
    "best_performing_services": [
        "service with highest win rate"
    ],
    "improvement_areas": [
        "area to improve 1",
        "area to improve 2"
    ],
    "recommendations": [
        "recommendation to improve win rate 1",
        "recommendation to improve win rate 2"
    ],
    "summary": "3-4 sentence win/loss analysis"
}}

Won Deals ({len(won)}):
{json.dumps([_client_summary(c) for c in won], indent=2)}

Lost Deals ({len(lost)}):
{json.dumps([_client_summary(c) for c in lost], indent=2)}"""

    return await generate_json(prompt)