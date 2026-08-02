from datetime import UTC, datetime, timedelta

import pytest

from bot.matchmaking import RankedMatchmakingPolicy
from bot.pvp_models import PvPQueueEntry, PvPQueueMode, PvPUser
from bot.ranked_pvp_store import RankedPvPStore
from tests.fake_redis import FakeRedis


def entry(
    user_id: int,
    *,
    rating: int = 1000,
    games: int = 10,
    mode: PvPQueueMode = PvPQueueMode.RANKED,
    queued_at: datetime | None = None,
) -> PvPQueueEntry:
    return PvPQueueEntry(
        participant=PvPUser(user_id=user_id, display_name=f"User {user_id}"),
        topic=f"Тема {user_id}",
        season="season-1",
        mode=mode,
        rating=rating,
        games=games,
        queued_at=queued_at or datetime.now(UTC),
    )


def test_ranked_search_gap_expands_and_caps() -> None:
    now = datetime(2026, 8, 2, 8, 0, tzinfo=UTC)
    policy = RankedMatchmakingPolicy(
        base_elo_gap=100,
        elo_gap_step=50,
        expand_interval_seconds=300,
        max_elo_gap=250,
    )
    queued = entry(1, queued_at=now - timedelta(minutes=20))

    assert policy.search_gap(entry(2), now=now) == 100
    assert policy.search_gap(queued, now=now) == 250


def test_ranked_modes_and_placement_groups_do_not_mix() -> None:
    policy = RankedMatchmakingPolicy()
    ranked = entry(1)
    open_entry = entry(2, mode=PvPQueueMode.OPEN)
    placement = entry(3, games=2)

    assert not policy.compatible(ranked, open_entry)
    assert not policy.compatible(ranked, placement)
    assert policy.compatible(placement, entry(4, games=4, rating=1080))


def test_oldest_ranked_search_window_can_expand() -> None:
    now = datetime(2026, 8, 2, 8, 0, tzinfo=UTC)
    policy = RankedMatchmakingPolicy(
        base_elo_gap=100,
        elo_gap_step=100,
        expand_interval_seconds=300,
        max_elo_gap=400,
    )
    waiting = entry(1, rating=900, queued_at=now - timedelta(minutes=15))
    newcomer = entry(2, rating=1200, queued_at=now)

    assert policy.compatible(waiting, newcomer, now=now)


@pytest.mark.asyncio
async def test_ranked_store_selects_closest_eligible_candidate() -> None:
    store = RankedPvPStore(FakeRedis(), prefix="ranked-test")
    far = entry(1, rating=900)
    close = entry(2, rating=1080)
    entrant = entry(3, rating=1100)
    await store._save_queue([far, close])

    match = await store.join_queue(entrant)

    assert match is not None
    assert {match.pro.user_id, match.con.user_id} == {2, 3}
    remaining = await store.get_queue_entry(1)
    assert remaining is not None
    assert remaining.rating == 900


@pytest.mark.asyncio
async def test_open_and_ranked_queues_are_isolated() -> None:
    store = RankedPvPStore(FakeRedis(), prefix="mode-test")

    assert await store.join_queue(entry(1, mode=PvPQueueMode.OPEN)) is None
    assert await store.join_queue(entry(2, mode=PvPQueueMode.RANKED)) is None

    assert await store.get_queue_entry(1) is not None
    assert await store.get_queue_entry(2) is not None


@pytest.mark.asyncio
async def test_placement_player_waits_for_placement_opponent() -> None:
    store = RankedPvPStore(FakeRedis(), prefix="placement-test")

    assert await store.join_queue(entry(1, games=2, rating=1000)) is None
    assert await store.join_queue(entry(2, games=10, rating=1000)) is None
    match = await store.join_queue(entry(3, games=4, rating=1050))

    assert match is not None
    assert {match.pro.user_id, match.con.user_id} == {1, 3}
    assert await store.get_queue_entry(2) is not None
