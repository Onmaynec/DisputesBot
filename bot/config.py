from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables or .env."""

    bot_token: SecretStr
    openai_api_key: SecretStr
    openai_model: str = "gpt-5.5"
    openai_base_url: str | None = None
    leaderboard_path: Path = Path("data/leaderboard.json")
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
