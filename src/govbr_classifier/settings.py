"""Runtime settings read from the environment (see .env.example)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """All configurable values in one place. Defaults are safe for local development."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    play_app_id: str = "br.gov.meugovbr"
    play_lang: str = "pt"
    play_country: str = "br"

    database_url: str = "sqlite:///./data/local/predictions.db"
    text_hash_salt: str = ""

    model_dir: Path = PROJECT_ROOT / "models" / "current"
    model_sha256: str = ""

    rate_limit: str = "30/minute"
    max_batch_size: int = 50

    # Contract limits (ADR-03). There is no minimum length: only empty or whitespace-only text is a
    # contract error; text with no letter or digit is out of distribution (guards/text_quality.py).
    max_text_chars: int = 2000

    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
