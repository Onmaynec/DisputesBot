from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables or .env."""

    bot_token: SecretStr
    openai_api_key: SecretStr
    openai_model: str = "gpt-5.5"
    openai_judge_model: str | None = None
    openai_base_url: str | None = None
    redis_url: str = "redis://localhost:6379/0"
    database_url: str = (
        "postgresql+asyncpg://disputesbot:disputesbot@localhost:5432/disputesbot"
    )
    database_echo: bool = False
    redis_prefix: str = "disputesbot"
    session_ttl_seconds: int = 604_800
    leaderboard_path: Path = Path("data/leaderboard.json")
    max_topic_chars: int = 300
    max_argument_chars: int = 2500
    rate_limit_requests: int = 5
    rate_limit_window_seconds: int = 20
    request_lock_ttl_seconds: int = 90
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
