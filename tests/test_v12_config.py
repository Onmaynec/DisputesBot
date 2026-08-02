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


def test_ranked_matchmaking_defaults() -> None:
    settings = make_settings()

    assert settings.pvp_ranked_base_elo_gap == 100
    assert settings.pvp_ranked_elo_gap_step == 50
    assert settings.pvp_ranked_expand_interval_seconds == 300
    assert settings.pvp_ranked_max_elo_gap == 400


@pytest.mark.parametrize(
    "field",
    [
        "pvp_ranked_base_elo_gap",
        "pvp_ranked_elo_gap_step",
        "pvp_ranked_expand_interval_seconds",
        "pvp_ranked_max_elo_gap",
    ],
)
def test_ranked_matchmaking_values_must_be_positive(field: str) -> None:
    with pytest.raises(ValidationError):
        make_settings(**{field: 0})


def test_ranked_max_gap_cannot_be_smaller_than_base() -> None:
    with pytest.raises(ValidationError):
        make_settings(pvp_ranked_base_elo_gap=200, pvp_ranked_max_elo_gap=100)
