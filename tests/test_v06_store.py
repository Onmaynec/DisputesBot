import pytest

from bot.pvp_models import PvPQueueEntry, PvPUser
from bot.pvp_store import PvPBusyError, PvPStore
from tests.fake_redis import FakeRedis


@pytest.mark.asyncio
async def test_store_tracks_and_cleans_active_match() -> None:
    redis = FakeRedis()
    store = PvPStore(redis, turn_timeout_seconds=60)
    match = await store.create_match(
        PvPUser(user_id=1, display_name="A"),
        PvPUser(user_id=2, display_name="B"),
        topic="Тема",
        season="s1",
        first_is_pro=True,
    )
    assert await store.active_count() == 1
    assert match.turn_deadline is not None
    await store.finish_match(match)
    assert await store.active_count() == 0


@pytest.mark.asyncio
async def test_blocked_pair_is_not_created() -> None:
    async def pair_allowed(first: int, second: int) -> bool:
        return {first, second} != {1, 2}

    store = PvPStore(FakeRedis(), pair_allowed=pair_allowed)
    with pytest.raises(PvPBusyError):
        await store.create_match(
            PvPUser(user_id=1, display_name="A"),
            PvPUser(user_id=2, display_name="B"),
            topic="Тема",
            season="s1",
        )


@pytest.mark.asyncio
async def test_queue_skips_blocked_candidate() -> None:
    async def pair_allowed(first: int, second: int) -> bool:
        return {first, second} != {1, 2}

    store = PvPStore(FakeRedis(), pair_allowed=pair_allowed)
    await store.join_queue(
        PvPQueueEntry(
            participant=PvPUser(user_id=1, display_name="A"),
            topic="Первая",
            season="s1",
        )
    )
    result = await store.join_queue(
        PvPQueueEntry(
            participant=PvPUser(user_id=2, display_name="B"),
            topic="Вторая",
            season="s1",
        )
    )
    assert result is None
    assert await store.queue_count() == 2
