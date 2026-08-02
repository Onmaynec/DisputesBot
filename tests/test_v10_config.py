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


def test_challenge_ttl_default() -> None:
    assert make_settings().pvp_challenge_ttl_hours == 24


@pytest.mark.parametrize("value", [0, 169])
def test_challenge_ttl_validates_range(value: int) -> None:
    with pytest.raises(ValidationError):
        make_settings(pvp_challenge_ttl_hours=value)
