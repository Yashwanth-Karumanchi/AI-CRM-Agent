import google.genai as genai
import json
from app.config import get_settings
from app.logger import get_logger
from app.services import sheets

logger = get_logger(__name__)

def get_gemini_client():
    settings = get_settings()
    client = genai.Client(api_key=settings.gemini_api_key)
    return client

async def extract_client_from_pdf(pdf_text: str) -> dict:
    """Use Gemini to extract structured client data from PDF text"""
    model = get_gemini_client()

    prompt = f"""
    Extract client information from the following document.
    Return ONLY a valid JSON object with these exact fields:
    {{
        "name": "full name or empty string",
        "email": "email address or empty string",
        "company": "company name or empty string",
        "phone": "phone number or empty string",
        "service": "service or product requested or empty string",
        "priority": "Low or Medium or High",
        "notes": "any other relevant information or empty string",
        "executive_summary": "2-3 sentence summary of the engagement",
        "business_problem": "what problem they are trying to solve",
        "current_process": "how they currently handle this",
        "recommendations": ["recommendation 1", "recommendation 2"],
        "open_questions": ["question 1", "question 2"]
    }}

    Do not include any explanation or markdown.
    Return only the JSON object.

    Document:
    {pdf_text[:4000]}
    """

    response = model.models.generate_content(
        model="models/gemini-2.5-flash",
        contents=prompt
    )
    text = response.text.strip()

    # Clean markdown if present
    text = text.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.error(f"Failed to parse Gemini response: {text}")
        raise ValueError("AI could not extract structured data from PDF")

async def analyze_client(client: dict) -> dict:
    """Deep analysis of a single client"""
    model = get_gemini_client()

    prompt = f"""
    Analyze this CRM client record and provide a detailed assessment.
    Return ONLY a valid JSON object with these fields:
    {{
        "executive_summary": "2-3 sentence overview",
        "business_problem": "their main challenge",
        "current_process": "how they work now",
        "recommendations": ["action 1", "action 2", "action 3"],
        "open_questions": ["question 1", "question 2"],
        "next_actions": ["immediate action 1", "immediate action 2"],
        "risk_level": "Low or Medium or High",
        "opportunity_score": "1-10 rating",
        "notes": "any other insights"
    }}

    Do not include any explanation or markdown.
    Return only the JSON object.

    Client Record:
    {json.dumps(client, indent=2)}
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
        raise ValueError("AI could not analyze client data")

async def draft_email(
    client: dict,
    instruction: str
) -> dict:
    """Use Gemini to draft a professional email"""
    model = get_gemini_client()

    prompt = f"""
    Draft a professional email based on these instructions.
    Return ONLY a valid JSON object with these fields:
    {{
        "subject": "email subject line",
        "body": "full email body text"
    }}

    Do not include any explanation or markdown.
    Return only the JSON object.

    Client Information:
    Name: {client.get('name')}
    Company: {client.get('company', 'N/A')}
    Email: {client.get('email', 'N/A')}
    Service: {client.get('service', 'N/A')}
    Stage: {client.get('stage')}
    Notes: {client.get('notes', 'N/A')}

    Email Instructions:
    {instruction}
    """

    response = model.models.generate_content(
        model="models/gemini-2.5-flash",
        contents=prompt
    )
    text = response.text.strip()
    text = text.replace("```json", "").replace("```", "").strip()

    try:
        result = json.loads(text)
        return {
            "subject": result.get("subject", ""),
            "body": result.get("body", "")
        }
    except json.JSONDecodeError:
        raise ValueError("AI could not draft email")

async def chat(
    message: str,
    client_id: str = None
) -> str:
    """General AI chat about CRM data"""
    model = get_gemini_client()

    # Get context
    context = ""
    if client_id:
        client = await sheets.get_client_by_id(client_id)
        if client:
            context = f"\nClient Context:\n{json.dumps(client, indent=2)}"
    else:
        # Get pipeline summary for general questions
        try:
            summary = await sheets.get_pipeline_summary()
            context = f"\nCRM Context:\n{json.dumps(summary, indent=2)}"
        except Exception:
            pass

    prompt = f"""
    You are an AI CRM assistant helping manage client relationships.
    Answer the following question professionally and concisely.
    {context}

    Question: {message}
    """

    response = model.models.generate_content(
        model="models/gemini-2.5-flash",
        contents=prompt
    )
    return response.text.strip()