import importlib.util
from datetime import UTC, datetime, timedelta

import pytest

if (
    importlib.util.find_spec("aiogram") is None
    or importlib.util.find_spec("aiosqlite") is None
):
    pytest.skip("aiogram and aiosqlite are installed in CI", allow_module_level=True)

from bot.database import Database
from bot.pvp_models import PvPUser
from bot.pvp_repository import PvPRepository
from bot.pvp_store import PvPStore
from bot.pvp_timeout import sweep_expired_matches
from tests.fake_redis import FakeRedis


class FakeBot:
    def __init__(self) -> None:
        self.messages: list[tuple[int, str]] = []

    async def send_message(self, user_id: int, text: str, **kwargs) -> None:
        del kwargs
        self.messages.append((user_id, text))


@pytest.mark.asyncio
async def test_timeout_sweep_records_started_match_once() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_all_for_tests()
    repository = PvPRepository(database.sessions)
    store = PvPStore(FakeRedis(), turn_timeout_seconds=60)
    match = await store.create_match(
        PvPUser(user_id=1, display_name="One"),
        PvPUser(user_id=2, display_name="Two"),
        topic="Тема",
        season="s1",
        first_is_pro=True,
    )
    match.add_argument(1, "Аргумент", turn_timeout_seconds=60)
    match.turn_deadline = datetime.now(UTC) - timedelta(seconds=1)
    await store.save_match(match)
    bot = FakeBot()

    assert await sweep_expired_matches(bot, store, repository) == 1
    assert await sweep_expired_matches(bot, store, repository) == 0
    history = await repository.history(1)

    assert len(history) == 1
    assert history[0].outcome == "timeout"
    assert await store.active_count() == 0
    assert len(bot.messages) == 2
    await database.close()
