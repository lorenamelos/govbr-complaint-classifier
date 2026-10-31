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
    # TEMPORARY: log the shape of IP headers, never their values (api/ip_diagnostics.py).
    rate_limit_diagnostics: bool = False
    max_batch_size: int = 50

    # Contract limits (ADR-03)
    min_text_chars: int = 3
    max_text_chars: int = 2000

    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
