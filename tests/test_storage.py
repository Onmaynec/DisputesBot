import json
from pathlib import Path

import pytest

from bot.models import DebateMode, Difficulty, TournamentScores
from bot.storage import LeaderboardStore, MemoryStore


@pytest.mark.asyncio
async def test_memory_store_restores_session_copy() -> None:
    store = MemoryStore()
    await store.set_role(7, "циник")
    await store.set_difficulty(7, Difficulty.EXPERT)
    session = await store.create_session(7, "Тема", DebateMode.DEBATE)
    session.add_user_argument("Аргумент")
    await store.save_session(7, session)

    restored = await store.get_session(7)

    assert restored is not None
    assert restored.role == "циник"
    assert restored.difficulty is Difficulty.EXPERT
    assert restored.user_argument_count == 1
    restored.topic = "Изменено локально"
    assert (await store.get_session(7)).topic == "Тема"  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_leaderboard_is_keyed_by_user_id_and_tracks_stats(tmp_path: Path) -> None:
    path = tmp_path / "leaderboard.json"
    store = LeaderboardStore(path)
    scores = TournamentScores(
        logic=8,
        argumentation=7,
        creativity=6,
        winner="user",
        reason="Пользователь лучше отвечал на возражения.",
    )

    await store.record_result(
        user_id=123,
        username="old_name",
        display_name="Test User",
        scores=scores,
    )
    await store.record_result(
        user_id=123,
        username="new_name",
        display_name="Test User",
        scores=scores,
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert list(payload) == ["123"]
    assert payload["123"]["username"] == "new_name"
    assert payload["123"]["tournaments"] == 2
    assert payload["123"]["wins"] == 2


@pytest.mark.asyncio
async def test_legacy_username_key_is_migrated_on_next_write(tmp_path: Path) -> None:
    path = tmp_path / "leaderboard.json"
    path.write_text(
        json.dumps(
            {
                "@legacy": {
                    "user_id": 55,
                    "username": "legacy",
                    "tournaments": 1,
                    "best_total": 20,
                    "average_total": 20,
                }
            }
        ),
        encoding="utf-8",
    )
    store = LeaderboardStore(path)
    scores = TournamentScores(
        logic=7,
        argumentation=7,
        creativity=7,
        winner="draw",
        reason="Стороны выступили сопоставимо.",
    )

    await store.record_result(
        user_id=55,
        username="renamed",
        display_name="Legacy User",
        scores=scores,
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert "@legacy" not in payload
    assert payload["55"]["tournaments"] == 2
    assert payload["55"]["draws"] == 1


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, object] = {}

    async def get(self, key: str) -> object | None:
        return self.values.get(key)

    async def set(self, key: str, value: object, **_: object) -> bool:
        self.values[key] = value
        return True

    async def mget(self, *keys: str) -> list[object | None]:
        return [self.values.get(key) for key in keys]

    async def delete(self, *keys: str) -> int:
        deleted = 0
        for key in keys:
            deleted += int(key in self.values)
            self.values.pop(key, None)
        return deleted

    async def getdel(self, key: str) -> object | None:
        return self.values.pop(key, None)

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_redis_store_restores_active_session() -> None:
    from bot.storage import RedisStore

    redis = FakeRedis()
    first_process = RedisStore(redis, prefix="test")
    session = await first_process.create_session(99, "Сохраняемая тема")
    session.add_user_argument("Аргумент до перезапуска")
    await first_process.save_session(99, session)

    second_process = RedisStore(redis, prefix="test")
    restored = await second_process.get_session(99)

    assert restored is not None
    assert restored.topic == "Сохраняемая тема"
    assert restored.user_argument_count == 1
    assert restored.history[-1].text == "Аргумент до перезапуска"
