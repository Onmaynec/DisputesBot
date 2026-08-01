from pydantic import SecretStr

from bot.config import Settings


def test_moderator_ids_parse_csv_and_semicolon() -> None:
    settings = Settings(
        bot_token=SecretStr("token"),
        openai_api_key=SecretStr("key"),
        moderator_user_ids="10, 20;30",
    )
    assert settings.moderator_ids == frozenset({10, 20, 30})
