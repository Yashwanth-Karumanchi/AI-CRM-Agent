import json
import re
import asyncio
from app.logger import get_logger

logger = get_logger(__name__)

# ── Cached Gemini client ───────────────────────────────
_gemini_client = None


def _get_gemini_client():
    """Return cached Gemini client"""
    global _gemini_client
    if _gemini_client is None:
        from app.config import get_settings
        import google.genai as genai
        settings = get_settings()
        _gemini_client = genai.Client(
            api_key=settings.gemini_api_key
        )
    return _gemini_client


async def generate(
    prompt: str,
    expect_json: bool = False,
    retries: int = 3
) -> str:
    """
    Central LLM generation — all AI calls go through here.
    Model configured via LLM_MODEL env var in config.py.
    Handles rate limits with exponential backoff.
    Never blocks the event loop.
    """
    from app.config import get_settings
    settings = get_settings()

    last_error = None

    for attempt in range(retries):
        try:
            # Run blocking Gemini call in thread pool
            def _sync_generate():
                client = _get_gemini_client()
                response = client.models.generate_content(
                    model=settings.llm_model,
                    contents=prompt
                )
                return response.text.strip()

            text = await asyncio.to_thread(_sync_generate)

            if expect_json:
                text = _clean_json(text)

            return text

        except Exception as e:
            last_error = e
            err = str(e)

            if "429" in err or "RESOURCE_EXHAUSTED" in err:
                # Exponential backoff: 20s, 40s, 60s
                wait = (attempt + 1) * 20
                logger.warning(
                    f"LLM rate limited. "
                    f"Waiting {wait}s "
                    f"(attempt {attempt + 1}/{retries})"
                )
                await asyncio.sleep(wait)

                if attempt == retries - 1:
                    raise ValueError(
                        "AI rate limit reached. "
                        "Please wait 30 seconds and try again."
                    )
                # Reset cached client on rate limit
                global _gemini_client
                _gemini_client = None
                continue

            elif "invalid_api_key" in err.lower() or \
                 "api_key" in err.lower():
                raise ValueError(
                    "Invalid Gemini API key. "
                    "Check GEMINI_API_KEY in Render."
                )

            elif "model" in err.lower() and \
                 "not found" in err.lower():
                raise ValueError(
                    f"Model '{settings.llm_model}' not found. "
                    f"Check LLM_MODEL in Render."
                )

            else:
                logger.error(
                    f"LLM generation failed "
                    f"(attempt {attempt + 1}): {e}"
                )
                # Retry once on unknown errors
                if attempt < retries - 1:
                    await asyncio.sleep(2)
                    continue
                raise

    raise ValueError(
        f"LLM generation failed after {retries} attempts: "
        f"{last_error}"
    )


async def generate_json(
    prompt: str,
    retries: int = 3
) -> dict:
    """
    Generate content and parse as JSON.
    Retries with a correction prompt if JSON is malformed.
    """
    for attempt in range(retries):
        try:
            text = await generate(
                prompt, expect_json=True
            )
            return json.loads(text)

        except json.JSONDecodeError as e:
            logger.warning(
                f"JSON parse failed (attempt {attempt + 1}): "
                f"{str(e)[:100]}"
            )

            if attempt < retries - 1:
                # Ask model to fix its output
                fix_prompt = (
                    f"The following is not valid JSON. "
                    f"Fix it and return ONLY valid JSON, "
                    f"no explanation, no markdown:\n\n{text}"
                )
                try:
                    text = await generate(
                        fix_prompt, expect_json=True
                    )
                    return json.loads(text)
                except Exception:
                    continue
            else:
                logger.error(
                    f"JSON parse failed after {retries} "
                    f"attempts. Raw: {text[:300]}"
                )
                raise ValueError(
                    "AI returned invalid JSON after retries. "
                    "Please try again."
                )

        except ValueError:
            # Rate limit or model error — propagate
            raise

    raise ValueError(
        f"generate_json failed after {retries} attempts"
    )


def _clean_json(text: str) -> str:
    """
    Strip markdown fences and extract JSON object.
    Handles: ```json...```, ``` ...```, text before/after {}
    """
    if not text:
        return "{}"

    text = text.strip()

    # Remove markdown fences
    text = re.sub(r'^```json\s*\n?', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^```\s*\n?', '', text)
    text = re.sub(r'\n?```\s*$', '', text)
    text = text.strip()

    # If there's text before the JSON, extract just the object
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        return match.group()

    # Try array
    match = re.search(r'\[.*\]', text, re.DOTALL)
    if match:
        return match.group()

    return text


def safe_str(val) -> str:
    """
    Safely convert any value to string for LLM prompts.
    Prevents unhashable type and other serialization errors.
    """
    if val is None:
        return ""
    if isinstance(val, bool):
        return str(val).lower()
    if isinstance(val, (dict, list)):
        try:
            return json.dumps(val)
        except Exception:
            return str(val)
    if isinstance(val, float):
        if val != val:  # NaN check
            return ""
        return str(val)
    return str(val)

async def generate_with_document(
    prompt: str,
    document_text: str,
    max_doc_chars: int = 6000
) -> str:
    """
    Generate LLM response with document context.
    Truncates document to avoid token limits.
    """
    truncated = document_text[:max_doc_chars]
    if len(document_text) > max_doc_chars:
        truncated += (
            f"\n\n[Document truncated at "
            f"{max_doc_chars} characters]"
        )

    full_prompt = (
        f"{prompt}\n\n"
        f"DOCUMENT CONTENT:\n"
        f"{'=' * 40}\n"
        f"{truncated}\n"
        f"{'=' * 40}"
    )

    return await generate(full_prompt)


async def generate_json_with_document(
    prompt: str,
    document_text: str,
    max_doc_chars: int = 6000
) -> dict:
    """
    Generate structured JSON response with document context.
    """
    truncated = document_text[:max_doc_chars]
    if len(document_text) > max_doc_chars:
        truncated += (
            f"\n\n[Document truncated at "
            f"{max_doc_chars} characters]"
        )

    full_prompt = (
        f"{prompt}\n\n"
        f"DOCUMENT CONTENT:\n"
        f"{'=' * 40}\n"
        f"{truncated}\n"
        f"{'=' * 40}"
    )

    return await generate_json(full_prompt)