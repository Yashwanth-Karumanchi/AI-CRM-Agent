import json
from typing import List, Optional
from app.logger import get_logger

logger = get_logger(__name__)

async def natural_language_search(
    query: str,
    clients: List[dict],
    model
) -> dict:
    """
    Search clients using natural language.
    Understands intent not just keywords.
    """

    prompt = f"""
    You are a CRM search engine.
    The user wants to find clients matching this query:
    "{query}"

    Analyze each client and return ONLY a valid JSON object:

    {{
        "matching_client_ids": ["CL-XXXX", "CL-YYYY"],
        "search_interpretation": "<how you interpreted the query>",
        "filters_applied": ["<filter 1>", "<filter 2>"],
        "total_matches": <integer>,
        "confidence": "<High|Medium|Low>",
        "suggestion": "<better search if no matches>"
    }}

    Available clients:
    {json.dumps([
        {{
            "client_id": c.get("client_id"),
            "name": c.get("name"),
            "company": c.get("company"),
            "email": c.get("email"),
            "service": c.get("service"),
            "priority": c.get("priority"),
            "stage": c.get("stage"),
            "notes": c.get("notes", "")[:200],
            "next_follow_up": c.get("next_follow_up")
        }}
        for c in clients
    ], indent=2)}

    Return only valid JSON. No explanation. No markdown.
    """

    response = model.models.generate_content(
        model="models/gemma-4-26b-a4b-it",
        contents=prompt
    )

    text = response.text.strip()
    text = text.replace("```json", "").replace("```", "").strip()

    try:
        result = json.loads(text)
        matching_ids = result.get("matching_client_ids", [])
        matched_clients = [
            c for c in clients
            if c.get("client_id") in matching_ids
        ]
        result["matched_clients"] = matched_clients
        return result
    except json.JSONDecodeError:
        logger.error(f"Search parse failed: {text}")
        raise ValueError("AI could not process search query")


async def detect_patterns(
    clients: List[dict],
    model
) -> dict:
    """
    Detect patterns across all clients.
    Find common traits, segments, and trends.
    """

    prompt = f"""
    Analyze these CRM clients and detect patterns.
    Return ONLY a valid JSON object:

    {{
        "total_analyzed": <integer>,
        "segments": [
            {{
                "segment_name": "<name>",
                "description": "<what defines this segment>",
                "client_ids": ["CL-XXXX"],
                "size": <integer>,
                "opportunity": "<Low|Medium|High>"
            }}
        ],
        "common_services": [
            {{
                "service": "<service name>",
                "count": <integer>,
                "win_rate": "<percentage>"
            }}
        ],
        "stage_bottlenecks": [
            {{
                "stage": "<stage name>",
                "issue": "<what the bottleneck is>",
                "recommendation": "<how to fix>"
            }}
        ],
        "priority_distribution": {{
            "High": <integer>,
            "Medium": <integer>,
            "Low": <integer>
        }},
        "key_insights": [
            "<insight 1>",
            "<insight 2>",
            "<insight 3>"
        ],
        "growth_opportunities": [
            "<opportunity 1>",
            "<opportunity 2>"
        ],
        "risks": [
            "<risk 1>",
            "<risk 2>"
        ],
        "summary": "<3-4 sentence analysis>"
    }}

    Client Data:
    {json.dumps([
        {{
            "client_id": c.get("client_id"),
            "name": c.get("name"),
            "company": c.get("company"),
            "service": c.get("service"),
            "priority": c.get("priority"),
            "stage": c.get("stage"),
            "notes": c.get("notes", "")[:100]
        }}
        for c in clients
    ], indent=2)}

    Return only valid JSON. No explanation. No markdown.
    """

    response = model.models.generate_content(
        model="models/gemma-4-26b-a4b-it",
        contents=prompt
    )

    text = response.text.strip()
    text = text.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        raise ValueError("AI could not detect patterns")


async def intelligent_filter(
    criteria: str,
    clients: List[dict],
    model
) -> dict:
    """
    Filter clients based on complex natural language criteria.
    Examples:
    - "clients who havent been contacted in 2 weeks"
    - "high value clients stuck in proposal stage"
    - "clients likely to churn"
    """

    from datetime import date
    today = date.today().isoformat()

    prompt = f"""
    Today is {today}.
    Filter these clients based on this criteria:
    "{criteria}"

    Return ONLY a valid JSON object:

    {{
        "matching_client_ids": ["CL-XXXX"],
        "criteria_interpretation": "<how you interpreted it>",
        "total_matches": <integer>,
        "reasoning": "<why these clients match>",
        "suggested_action": "<what to do with these clients>"
    }}

    Clients:
    {json.dumps([
        {{
            "client_id": c.get("client_id"),
            "name": c.get("name"),
            "company": c.get("company"),
            "service": c.get("service"),
            "priority": c.get("priority"),
            "stage": c.get("stage"),
            "next_follow_up": c.get("next_follow_up", ""),
            "notes": c.get("notes", "")[:100],
            "created_at": c.get("created_at", "")
        }}
        for c in clients
    ], indent=2)}

    Return only valid JSON. No explanation. No markdown.
    """

    response = model.models.generate_content(
        model="models/gemma-4-26b-a4b-it",
        contents=prompt
    )

    text = response.text.strip()
    text = text.replace("```json", "").replace("```", "").strip()

    try:
        result = json.loads(text)
        matching_ids = result.get("matching_client_ids", [])
        matched_clients = [
            c for c in clients
            if c.get("client_id") in matching_ids
        ]
        result["matched_clients"] = matched_clients
        return result
    except json.JSONDecodeError:
        raise ValueError("AI could not process filter criteria")


async def revenue_forecast(
    clients: List[dict],
    model
) -> dict:
    """
    AI forecasts potential revenue from pipeline.
    """

    prompt = f"""
    Analyze this sales pipeline and forecast revenue.
    Return ONLY a valid JSON object:

    {{
        "total_pipeline_value": "<estimated total opportunity value>",
        "expected_revenue_30_days": "<expected revenue in 30 days>",
        "expected_revenue_90_days": "<expected revenue in 90 days>",
        "confidence_level": "<High|Medium|Low>",
        "high_confidence_deals": [
            {{
                "client_id": "<id>",
                "name": "<name>",
                "estimated_value": "<value>",
                "close_probability": <integer>,
                "expected_close_date": "<date>"
            }}
        ],
        "at_risk_revenue": "<revenue that might be lost>",
        "recommendations": [
            "<action to increase revenue 1>",
            "<action to increase revenue 2>"
        ],
        "assumptions": [
            "<assumption 1>",
            "<assumption 2>"
        ],
        "summary": "<3-4 sentence forecast summary>"
    }}

    Pipeline Data:
    Total Clients: {len(clients)}
    {json.dumps([
        {{
            "client_id": c.get("client_id"),
            "name": c.get("name"),
            "company": c.get("company"),
            "service": c.get("service"),
            "priority": c.get("priority"),
            "stage": c.get("stage"),
            "notes": c.get("notes", "")[:100]
        }}
        for c in clients
    ], indent=2)}

    Return only valid JSON. No explanation. No markdown.
    """

    response = model.models.generate_content(
        model="models/gemma-4-26b-a4b-it",
        contents=prompt
    )

    text = response.text.strip()
    text = text.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        raise ValueError("AI could not generate forecast")


async def win_loss_analysis(
    clients: List[dict],
    model
) -> dict:
    """
    Analyze won and lost deals for patterns.
    """

    won = [c for c in clients if c.get("stage") == "Won"]
    lost = [c for c in clients if c.get("stage") == "Lost"]

    prompt = f"""
    Analyze these won and lost deals.
    Return ONLY a valid JSON object:

    {{
        "total_won": {len(won)},
        "total_lost": {len(lost)},
        "win_rate": "<percentage>",
        "winning_patterns": [
            "<pattern that appears in won deals 1>",
            "<pattern that appears in won deals 2>"
        ],
        "losing_patterns": [
            "<pattern that appears in lost deals 1>",
            "<pattern that appears in lost deals 2>"
        ],
        "best_performing_services": [
            "<service with highest win rate 1>",
            "<service with highest win rate 2>"
        ],
        "improvement_areas": [
            "<area to improve 1>",
            "<area to improve 2>"
        ],
        "recommendations": [
            "<recommendation to improve win rate 1>",
            "<recommendation to improve win rate 2>"
        ],
        "summary": "<3-4 sentence analysis>"
    }}

    Won Deals:
    {json.dumps([
        {{
            "name": c.get("name"),
            "company": c.get("company"),
            "service": c.get("service"),
            "priority": c.get("priority"),
            "notes": c.get("notes", "")[:100]
        }}
        for c in won
    ], indent=2)}

    Lost Deals:
    {json.dumps([
        {{
            "name": c.get("name"),
            "company": c.get("company"),
            "service": c.get("service"),
            "priority": c.get("priority"),
            "notes": c.get("notes", "")[:100]
        }}
        for c in lost
    ], indent=2)}

    Return only valid JSON. No explanation. No markdown.
    """

    response = model.models.generate_content(
        model="models/gemma-4-26b-a4b-it",
        contents=prompt
    )

    text = response.text.strip()
    text = text.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        raise ValueError("AI could not analyze win/loss")