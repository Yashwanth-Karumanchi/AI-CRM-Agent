import json
from typing import List
from app.logger import get_logger
from app.services.llm import generate_json, safe_str

logger = get_logger(__name__)

# Cap clients sent to LLM to avoid token limits
MAX_SEARCH_CLIENTS = 100
MAX_PATTERN_CLIENTS = 80
MAX_FORECAST_CLIENTS = 80


def _client_summary(c: dict) -> dict:
    """Minimal client dict for LLM prompts"""
    return {
        "client_id": safe_str(c.get("client_id")),
        "name": safe_str(c.get("name")),
        "company": safe_str(c.get("company")),
        "email": safe_str(c.get("email")),
        "service": safe_str(c.get("service")),
        "priority": safe_str(c.get("priority")),
        "stage": safe_str(c.get("stage")),
        "notes": safe_str(c.get("notes"))[:120],
        "next_follow_up": safe_str(
            c.get("next_follow_up")
        ),
        "created_at": safe_str(c.get("created_at"))
    }


async def natural_language_search(
    query: str,
    clients: List[dict]
) -> dict:
    """
    Search clients using natural language.
    Returns matched clients with reasoning.
    """
    if not clients:
        return {
            "matching_client_ids": [],
            "matched_clients": [],
            "search_interpretation": "No clients in CRM",
            "total_matches": 0,
            "confidence": "Low",
            "suggestion": "Add clients to the CRM first"
        }

    # Cap for token safety
    sample = clients[:MAX_SEARCH_CLIENTS]

    prompt = f"""You are a CRM search engine.
Find clients matching this query: "{query}"

Return ONLY valid JSON:
{{
    "matching_client_ids": ["CL-XXXX", "CL-YYYY"],
    "search_interpretation": "how you understood the query",
    "filters_applied": ["filter 1", "filter 2"],
    "total_matches": 2,
    "confidence": "High",
    "suggestion": "better search if no good matches found"
}}

confidence values: High / Medium / Low

Available Clients ({len(sample)} total):
{json.dumps([_client_summary(c) for c in sample], indent=2)}"""

    result = await generate_json(prompt)

    matching_ids = result.get("matching_client_ids", [])
    # Always include matched_clients in response
    result["matched_clients"] = [
        c for c in clients
        if c.get("client_id") in matching_ids
    ]
    result["total_matches"] = len(
        result["matched_clients"]
    )

    return result


async def detect_patterns(clients: List[dict]) -> dict:
    """
    Detect patterns, segments and opportunities
    across the pipeline.
    """
    if not clients:
        return {
            "total_analyzed": 0,
            "summary": "No clients to analyze.",
            "segments": [],
            "key_insights": [],
            "growth_opportunities": [],
            "risks": []
        }

    sample = clients[:MAX_PATTERN_CLIENTS]

    # Pre-compute priority distribution
    pri_dist = {"High": 0, "Medium": 0, "Low": 0}
    for c in clients:
        p = c.get("priority", "Medium")
        if p in pri_dist:
            pri_dist[p] += 1

    prompt = f"""You are a CRM analyst detecting pipeline patterns.
Return ONLY valid JSON:
{{
    "total_analyzed": {len(sample)},
    "segments": [
        {{
            "segment_name": "descriptive name",
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
            "issue": "specific bottleneck",
            "recommendation": "specific fix"
        }}
    ],
    "priority_distribution": {json.dumps(pri_dist)},
    "key_insights": [
        "specific insight 1",
        "specific insight 2",
        "specific insight 3"
    ],
    "growth_opportunities": [
        "specific opportunity 1",
        "specific opportunity 2"
    ],
    "risks": [
        "specific risk 1",
        "specific risk 2"
    ],
    "summary": "3-4 sentence analysis of the pipeline"
}}

opportunity values: High / Medium / Low

Client Data ({len(sample)} of {len(clients)} clients):
{json.dumps([_client_summary(c) for c in sample], indent=2)}"""

    return await generate_json(prompt)


async def intelligent_filter(
    criteria: str,
    clients: List[dict]
) -> dict:
    """
    Filter clients using complex natural language criteria.
    More specific than search — focused on conditions.
    """
    from datetime import date
    today = date.today().isoformat()

    if not clients:
        return {
            "matching_client_ids": [],
            "matched_clients": [],
            "criteria_interpretation": "No clients in CRM",
            "total_matches": 0,
            "reasoning": "No clients available",
            "suggested_action": "Add clients first"
        }

    sample = clients[:MAX_SEARCH_CLIENTS]

    prompt = f"""Today is {today}. You are a CRM filter engine.
Filter clients matching: "{criteria}"

Return ONLY valid JSON:
{{
    "matching_client_ids": ["CL-XXXX"],
    "criteria_interpretation": "how you interpreted the criteria",
    "total_matches": 1,
    "reasoning": "why these specific clients match",
    "suggested_action": "what to do with these clients"
}}

Use today's date ({today}) for any time-based filters.

Clients ({len(sample)} total):
{json.dumps([_client_summary(c) for c in sample], indent=2)}"""

    result = await generate_json(prompt)

    matching_ids = result.get("matching_client_ids", [])
    result["matched_clients"] = [
        c for c in clients
        if c.get("client_id") in matching_ids
    ]
    result["total_matches"] = len(
        result["matched_clients"]
    )

    return result


async def revenue_forecast(clients: List[dict]) -> dict:
    """
    Forecast pipeline revenue based on stages
    and client data.
    """
    if not clients:
        return {
            "total_pipeline_value": "$0",
            "expected_revenue_30_days": "$0",
            "expected_revenue_90_days": "$0",
            "confidence_level": "Low",
            "summary": "No clients in pipeline to forecast.",
            "high_confidence_deals": [],
            "recommendations": [],
            "assumptions": []
        }

    # Focus on active pipeline (not Won/Lost)
    active = [
        c for c in clients
        if c.get("stage") not in ("Won", "Lost")
    ]
    won = [c for c in clients if c.get("stage") == "Won"]

    sample = clients[:MAX_FORECAST_CLIENTS]

    prompt = f"""You are a CRM revenue analyst.
Forecast revenue from this pipeline.
Return ONLY valid JSON:
{{
    "total_pipeline_value": "estimated range e.g. $50K-$150K",
    "expected_revenue_30_days": "e.g. $15,000-$30,000",
    "expected_revenue_90_days": "e.g. $45,000-$90,000",
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
    "at_risk_revenue": "e.g. $20,000 at risk",
    "recommendations": [
        "specific action to increase revenue 1",
        "specific action to increase revenue 2"
    ],
    "assumptions": [
        "assumption 1",
        "assumption 2"
    ],
    "summary": "3-4 sentence forecast summary"
}}

confidence_level values: High / Medium / Low

Pipeline Stats:
- Total Clients: {len(clients)}
- Active (not Won/Lost): {len(active)}
- Already Won: {len(won)}

Client Data ({len(sample)} shown):
{json.dumps([_client_summary(c) for c in sample], indent=2)}"""

    return await generate_json(prompt)


async def win_loss_analysis(clients: List[dict]) -> dict:
    """
    Analyze patterns in won and lost deals.
    """
    won = [
        c for c in clients
        if c.get("stage") == "Won"
    ]
    lost = [
        c for c in clients
        if c.get("stage") == "Lost"
    ]

    if not won and not lost:
        return {
            "total_won": 0,
            "total_lost": 0,
            "win_rate": "0%",
            "summary": (
                "No won or lost deals to analyze yet. "
                "Close some deals to see patterns."
            ),
            "winning_patterns": [],
            "losing_patterns": [],
            "recommendations": []
        }

    win_rate = (
        round(len(won) / (len(won) + len(lost)) * 100)
        if (len(won) + len(lost)) > 0 else 0
    )

    prompt = f"""You are a CRM analyst examining won/lost deals.
Return ONLY valid JSON:
{{
    "total_won": {len(won)},
    "total_lost": {len(lost)},
    "win_rate": "{win_rate}%",
    "winning_patterns": [
        "specific pattern in won deals 1",
        "specific pattern in won deals 2",
        "specific pattern in won deals 3"
    ],
    "losing_patterns": [
        "specific pattern in lost deals 1",
        "specific pattern in lost deals 2"
    ],
    "best_performing_services": [
        "service type with highest win rate"
    ],
    "improvement_areas": [
        "specific area to improve 1",
        "specific area to improve 2"
    ],
    "recommendations": [
        "specific recommendation 1",
        "specific recommendation 2",
        "specific recommendation 3"
    ],
    "summary": "3-4 sentence win/loss analysis"
}}

Won Deals ({len(won)}):
{json.dumps([_client_summary(c) for c in won[:30]], indent=2)}

Lost Deals ({len(lost)}):
{json.dumps([_client_summary(c) for c in lost[:20]], indent=2)}"""

    return await generate_json(prompt)