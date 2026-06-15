from pydantic_settings import BaseSettings
from functools import lru_cache
import os

class Settings(BaseSettings):
    gemini_api_key: str
    spreadsheet_id: str
    api_username: str
    api_password: str
    gmail_address: str

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings() -> Settings:
    return Settings()