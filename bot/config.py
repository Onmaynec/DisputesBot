from pathlib import Path

from pydantic import SecretStr, field_validator, model_validator
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
    pvp_season: str = "season-1"
    pvp_match_ttl_seconds: int = 86_400
    pvp_invitation_ttl_seconds: int = 600
    pvp_queue_ttl_seconds: int = 1_800
    pvp_ranked_base_elo_gap: int = 100
    pvp_ranked_elo_gap_step: int = 50
    pvp_ranked_expand_interval_seconds: int = 300
    pvp_ranked_max_elo_gap: int = 400
    pvp_turn_timeout_seconds: int = 3_600
    pvp_timeout_sweep_seconds: int = 30
    pvp_repeat_window_seconds: int = 86_400
    pvp_max_rated_pair_matches: int = 3
    pvp_daily_reset_hour_utc: int = 0
    pvp_daily_reward_multiplier: int = 1
    pvp_stats_window_days: int = 30
    pvp_challenge_ttl_hours: int = 24
    moderator_user_ids: str = ""
    log_level: str = "INFO"

    @field_validator("pvp_daily_reset_hour_utc")
    @classmethod
    def validate_reset_hour(cls, value: int) -> int:
        if not 0 <= value <= 23:
            raise ValueError("PVP_DAILY_RESET_HOUR_UTC must be between 0 and 23")
        return value

    @field_validator("pvp_daily_reward_multiplier")
    @classmethod
    def validate_reward_multiplier(cls, value: int) -> int:
        if not 1 <= value <= 10:
            raise ValueError("PVP_DAILY_REWARD_MULTIPLIER must be between 1 and 10")
        return value

    @field_validator("pvp_stats_window_days")
    @classmethod
    def validate_stats_window(cls, value: int) -> int:
        if not 1 <= value <= 365:
            raise ValueError("PVP_STATS_WINDOW_DAYS must be between 1 and 365")
        return value

    @field_validator("pvp_challenge_ttl_hours")
    @classmethod
    def validate_challenge_ttl(cls, value: int) -> int:
        if not 1 <= value <= 168:
            raise ValueError("PVP_CHALLENGE_TTL_HOURS must be between 1 and 168")
        return value

    @field_validator(
        "pvp_ranked_base_elo_gap",
        "pvp_ranked_elo_gap_step",
        "pvp_ranked_expand_interval_seconds",
        "pvp_ranked_max_elo_gap",
    )
    @classmethod
    def validate_ranked_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("Ranked matchmaking values must be positive")
        return value

    @model_validator(mode="after")
    def validate_ranked_gap_bounds(self) -> "Settings":
        if self.pvp_ranked_max_elo_gap < self.pvp_ranked_base_elo_gap:
            raise ValueError(
                "PVP_RANKED_MAX_ELO_GAP must be at least PVP_RANKED_BASE_ELO_GAP"
            )
        return self

    @property
    def moderator_ids(self) -> frozenset[int]:
        values: set[int] = set()
        for raw in self.moderator_user_ids.replace(";", ",").split(","):
            normalized = raw.strip()
            if normalized:
                values.add(int(normalized))
        return frozenset(values)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
