"""Environment-based configuration for the API and external services."""

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)


@dataclass(frozen=True)
class Settings:
    database_url: str | None
    admin_password: str | None
    session_secret: str | None
    kanoon_api_token: str | None
    kanoon_api_base_url: str
    kanoon_max_api_calls_per_request: int
    kanoon_max_docs_per_request: int
    gemini_api_key: str | None
    gemini_model: str


def get_settings() -> Settings:
    max_calls = int(os.getenv("KANOON_MAX_API_CALLS_PER_REQUEST", "28"))
    max_docs = int(os.getenv("KANOON_MAX_DOCS_PER_REQUEST", "25"))
    if max_calls < 3:
        raise ValueError("KANOON_MAX_API_CALLS_PER_REQUEST must allow three search calls.")
    if not 1 <= max_docs <= 25:
        raise ValueError("KANOON_MAX_DOCS_PER_REQUEST must be between 1 and 25.")

    return Settings(
        # The dedicated external-DB variable avoids Replit's runtime-managed
        # DATABASE_URL, which may point at a different database.
        database_url=os.getenv("NEON_DATABASE_URL"),
        admin_password=os.getenv("ADMIN_PASSWORD"),
        session_secret=os.getenv("SESSION_SECRET"),
        kanoon_api_token=os.getenv("KANOON_API_TOKEN"),
        kanoon_api_base_url=os.getenv(
            "KANOON_API_BASE_URL", "https://api.indiankanoon.org"
        ).rstrip("/"),
        kanoon_max_api_calls_per_request=max_calls,
        kanoon_max_docs_per_request=max_docs,
        gemini_api_key=os.getenv("GEMINI_API_KEY"),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
    )


settings = get_settings()