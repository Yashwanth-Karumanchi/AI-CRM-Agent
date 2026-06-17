from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ── API Keys ───────────────────────────────────────
    gemini_api_key: str

    # ── Google Sheets ──────────────────────────────────
    spreadsheet_id: str

    # ── Auth ───────────────────────────────────────────
    api_username: str
    api_password: str

    # ── Gmail ──────────────────────────────────────────
    gmail_address: str

    # ── LLM Config ─────────────────────────────────────
    # Change model here or via LLM_MODEL env var in Render
    llm_model: str = "models/gemini-3.1-flash-lite"

    class Config:
        env_file = ".env"
        extra = "ignore"  # ignore unknown env vars


@lru_cache()
def get_settings() -> Settings:
    return Settings()