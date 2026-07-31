import json

from bot.judge_utils import anonymize_history, translate_winner
from bot.models import DebateSession


def test_anonymized_history_hides_author_names() -> None:
    session = DebateSession(topic="Тема", role="философ")
    session.add_user_argument("Тезис пользователя")
    session.add_bot_argument("Тезис бота")

    raw, participant_a = anonymize_history(session)
    payload = json.loads(raw)

    assert participant_a in {"user", "bot"}
    assert {item["participant"] for item in payload} == {"A", "B"}
    assert "user" not in raw
    assert "bot" not in raw


def test_winner_translation_respects_randomized_order() -> None:
    assert translate_winner("A", "user") == "user"
    assert translate_winner("B", "user") == "bot"
    assert translate_winner("A", "bot") == "bot"
    assert translate_winner("B", "bot") == "user"
    assert translate_winner("draw", "user") == "draw"
