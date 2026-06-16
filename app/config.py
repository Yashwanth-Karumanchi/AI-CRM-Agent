from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # API Keys
    gemini_api_key: str
    groq_api_key: str = ""

    # Google
    spreadsheet_id: str

    # Auth
    api_username: str
    api_password: str

    # Gmail
    gmail_address: str

    # LLM Config — change model here, affects everywhere
    llm_model: str = "models/gemini-2.5-flash-lite"
    llm_temperature: float = 0.3
    llm_max_tokens: int = 2048

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


# ── Model shortcuts ────────────────────────────────────
def get_model_name() -> str:
    return get_settings().llm_model