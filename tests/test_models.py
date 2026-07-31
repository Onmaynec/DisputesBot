from pydantic import ValidationError

from bot.models import (
    DebateMode,
    DebateSession,
    Difficulty,
    Stance,
    TournamentScores,
)
from bot.schemas import ArgumentOutput


def test_session_roundtrip_preserves_state() -> None:
    session = DebateSession(
        topic="Тестовая тема",
        role="юрист",
        difficulty=Difficulty.EXPERT,
        mode=DebateMode.TOURNAMENT,
    )
    session.set_stance(Stance.PRO)
    session.add_bot_argument("Первый аргумент бота с достаточной длиной.")
    session.add_user_argument("Аргумент пользователя")

    restored = DebateSession.model_validate_json(session.model_dump_json())

    assert restored == session
    assert restored.bot_stance is Stance.CON
    assert restored.user_arguments_in_round == 1
    assert restored.bot_arguments_in_round == 1


def test_structured_scores_reject_out_of_range_values() -> None:
    try:
        TournamentScores(
            logic=11,
            argumentation=5,
            creativity=5,
            winner="draw",
            reason="Валидное обоснование",
        )
    except ValidationError:
        pass
    else:
        raise AssertionError("Expected strict score validation")


def test_argument_schema_rejects_short_text() -> None:
    try:
        ArgumentOutput(argument="Слишком коротко")
    except ValidationError:
        pass
    else:
        raise AssertionError("Expected minimum argument length validation")
