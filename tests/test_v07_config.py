import pytest
from pydantic import ValidationError

from bot.config import Settings


def make_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "bot_token": "token",
        "openai_api_key": "key",
    }
    values.update(overrides)
    return Settings(**values)


def test_progression_settings_defaults() -> None:
    settings = make_settings()

    assert settings.pvp_daily_reset_hour_utc == 0
    assert settings.pvp_daily_reward_multiplier == 1
    assert settings.pvp_stats_window_days == 30


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("pvp_daily_reset_hour_utc", 24),
        ("pvp_daily_reward_multiplier", 0),
        ("pvp_stats_window_days", 366),
    ],
)
def test_progression_settings_validate_ranges(field: str, value: int) -> None:
    with pytest.raises(ValidationError):
        make_settings(**{field: value})
