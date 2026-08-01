import pytest

aiosqlite = pytest.importorskip("aiosqlite")

from bot.database import Database
from bot.models import DebateMode, Stance, TournamentScores
from bot.sql_profile_store import SQLProfileStore
from bot.storage import MemoryStore


@pytest.mark.asyncio
async def test_sql_repository_is_idempotent_and_deletes_cascade() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_all_for_tests()
    sessions = MemoryStore()
    repository = SQLProfileStore(database.sessions, sessions)
    session = await sessions.create_session(7, "Тест", DebateMode.TOURNAMENT)
    session.set_stance(Stance.PRO)
    session.add_user_argument("Аргумент")
    session.add_bot_argument("Контраргумент")
    await sessions.save_session(7, session)
    scores = TournamentScores(
        logic=8,
        argumentation=7,
        creativity=6,
        winner="user",
        reason="Пользователь лучше ответил на возражения.",
    )

    await repository.record_result(
        user_id=7,
        username="tester",
        display_name="Test User",
        scores=scores,
    )
    await repository.record_result(
        user_id=7,
        username="tester",
        display_name="Test User",
        scores=scores,
    )

    profile = await repository.get_user(7)
    assert profile is not None
    assert profile["tournaments"] == 1
    assert len(await repository.history(7)) == 1
    assert await repository.delete_user(7)
    assert await repository.get_user(7) is None
    assert await repository.history(7) == []
    await database.close()
