import json
import re
import asyncio
from app.logger import get_logger

logger = get_logger(__name__)


async def generate(
    prompt: str,
    expect_json: bool = False,
    retries: int = 3
) -> str:
    """
    Central LLM generation.
    All AI calls go through here.
    Change model in config.py or .env LLM_MODEL.
    """
    from app.config import get_settings
    settings = get_settings()

    for attempt in range(retries):
        try:
            import google.genai as genai
            client = genai.Client(
                api_key=settings.gemini_api_key
            )
            response = client.models.generate_content(
                model=settings.llm_model,
                contents=prompt
            )
            text = response.text.strip()

            if expect_json:
                text = _clean_json(text)

            return text

        except Exception as e:
            err = str(e)
            if "429" in err or "RESOURCE_EXHAUSTED" in err:
                wait = (attempt + 1) * 20
                logger.warning(
                    f"Rate limited. Waiting {wait}s... "
                    f"(attempt {attempt + 1}/{retries})"
                )
                await asyncio.sleep(wait)
                if attempt == retries - 1:
                    raise ValueError(
                        "Rate limit exceeded. "
                        "Please wait a moment and try again."
                    )
            else:
                logger.error(f"LLM generation failed: {e}")
                raise

    raise ValueError("LLM generation failed after retries")


async def generate_json(prompt: str) -> dict:
    """Generate and parse JSON response"""
    text = await generate(prompt, expect_json=True)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse failed: {text[:200]}")
        raise ValueError(f"AI returned invalid JSON: {e}")


def _clean_json(text: str) -> str:
    """Remove markdown fences and extract JSON"""
    text = text.strip()
    text = re.sub(r'^```json\s*', '', text)
    text = re.sub(r'^```\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    text = text.strip()

    # Extract JSON object if surrounded by text
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        return match.group()

    return text


def safe_str(val) -> str:
    """Safely convert any value to string"""
    if val is None:
        return ""
    if isinstance(val, (dict, list)):
        return json.dumps(val)
    return str(val)