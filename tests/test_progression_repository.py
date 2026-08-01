import importlib.util
from datetime import UTC, datetime, timedelta

import pytest

from bot.database import Database, PvPMatchRow, PvPPlayerRow, UserProfileRow
from bot.progression_repository import ProgressionRepository
from bot.pvp_models import PvPUser

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("aiosqlite") is None,
    reason="aiosqlite is not installed in the local sandbox",
)


async def add_profiles(database: Database, *user_ids: int) -> None:
    async with database.sessions.begin() as db:
        for user_id in user_ids:
            if await db.get(UserProfileRow, user_id) is None:
                db.add(
                    UserProfileRow(
                        user_id=user_id,
                        display_name=f"User {user_id}",
                    )
                )


async def add_match(
    database: Database,
    *,
    match_id: str,
    pro_user_id: int,
    con_user_id: int,
    winner_user_id: int | None,
    ended_at: datetime,
    rated: bool = True,
    pro_before: int = 1000,
    pro_after: int = 1000,
    con_before: int = 1000,
    con_after: int = 1000,
) -> None:
    async with database.sessions.begin() as db:
        db.add(
            PvPMatchRow(
                match_id=match_id,
                season="season-1",
                topic="Тестовая тема",
                pair_key=f"{min(pro_user_id, con_user_id)}:{max(pro_user_id, con_user_id)}",
                pro_user_id=pro_user_id,
                con_user_id=con_user_id,
                winner_user_id=winner_user_id,
                outcome="draw" if winner_user_id is None else "judged",
                rated=rated,
                unrated_reason=None if rated else "test",
                pro_rating_before=pro_before,
                pro_rating_after=pro_after,
                con_rating_before=con_before,
                con_rating_after=con_after,
                pro_scores={},
                con_scores={},
                reason="Тест",
                transcript=[],
                started_at=ended_at - timedelta(minutes=10),
                ended_at=ended_at,
            )
        )


@pytest.mark.asyncio
async def test_daily_claim_is_idempotent_and_tracks_streak() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_all_for_tests()
    await add_profiles(database, 1, 2, 3)
    repository = ProgressionRepository(database.sessions)
    first_day = datetime(2026, 8, 1, 12, tzinfo=UTC)

    await add_match(
        database,
        match_id="day1-a",
        pro_user_id=1,
        con_user_id=2,
        winner_user_id=1,
        ended_at=first_day - timedelta(hours=2),
        pro_after=1016,
        con_after=984,
    )
    await add_match(
        database,
        match_id="day1-b",
        pro_user_id=1,
        con_user_id=3,
        winner_user_id=1,
        ended_at=first_day - timedelta(hours=1),
        pro_before=1016,
        pro_after=1031,
        con_after=985,
    )

    user = PvPUser(user_id=1, display_name="User 1")
    first = await repository.claim_daily(user, "season-1", now=first_day)
    duplicate = await repository.claim_daily(user, "season-1", now=first_day)

    assert len(first.claimed_quest_ids) == 3
    assert first.gained_tokens > 0
    assert first.wallet.current_daily_streak == 1
    assert duplicate.claimed_quest_ids == ()
    assert duplicate.gained_tokens == 0
    assert duplicate.wallet.tokens == first.wallet.tokens

    second_day = first_day + timedelta(days=1)
    await add_match(
        database,
        match_id="day2-a",
        pro_user_id=1,
        con_user_id=2,
        winner_user_id=1,
        ended_at=second_day - timedelta(hours=2),
    )
    await add_match(
        database,
        match_id="day2-b",
        pro_user_id=1,
        con_user_id=3,
        winner_user_id=1,
        ended_at=second_day - timedelta(hours=1),
    )
    next_claim = await repository.claim_daily(user, "season-1", now=second_day)

    assert len(next_claim.claimed_quest_ids) == 3
    assert next_claim.wallet.current_daily_streak == 2
    assert next_claim.wallet.best_daily_streak == 2
    await database.close()


@pytest.mark.asyncio
async def test_analytics_splits_rated_matches_and_stances() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_all_for_tests()
    await add_profiles(database, 1, 2, 3)
    now = datetime(2026, 8, 1, 12, tzinfo=UTC)
    async with database.sessions.begin() as db:
        db.add(
            PvPPlayerRow(
                user_id=1,
                season="season-1",
                rating=1016,
                games=3,
                wins=1,
                draws=1,
                losses=1,
            )
        )
    await add_match(
        database,
        match_id="stats-a",
        pro_user_id=1,
        con_user_id=2,
        winner_user_id=1,
        ended_at=now - timedelta(days=2),
        pro_after=1016,
        con_after=984,
    )
    await add_match(
        database,
        match_id="stats-b",
        pro_user_id=3,
        con_user_id=1,
        winner_user_id=None,
        ended_at=now - timedelta(days=1),
        pro_before=1000,
        pro_after=1000,
        con_before=1016,
        con_after=1016,
    )
    await add_match(
        database,
        match_id="stats-c",
        pro_user_id=1,
        con_user_id=2,
        winner_user_id=2,
        ended_at=now - timedelta(hours=1),
        rated=False,
        pro_before=1016,
        pro_after=1016,
        con_before=984,
        con_after=984,
    )
    repository = ProgressionRepository(database.sessions, stats_window_days=30)

    stats = await repository.analytics(1, "season-1", now=now)

    assert stats.total_matches == 3
    assert stats.rated_matches == 2
    assert stats.unrated_matches == 1
    assert (stats.wins, stats.draws, stats.losses) == (1, 1, 1)
    assert stats.unique_opponents == 2
    assert stats.rating_delta_window == 16
    assert stats.current_win_streak == 0
    assert stats.best_win_streak == 1
    assert (stats.pro_matches, stats.pro_wins) == (2, 1)
    assert (stats.con_matches, stats.con_wins) == (1, 0)
    assert stats.rank == 1
    await database.close()
