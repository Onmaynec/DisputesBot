import importlib.util
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from bot.database import (
    Database,
    PvPMatchRow,
    PvPPlayerRow,
    PvPProgressionRow,
    UserProfileRow,
)
from bot.league_models import LeagueId
from bot.pvp_models import PvPUser
from bot.ranked_reward_database import PvPRankedRewardClaimRow
from bot.ranked_reward_repository import RankedRewardRepository

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("aiosqlite") is None,
    reason="aiosqlite is not installed in the local sandbox",
)


def user(user_id: int) -> PvPUser:
    return PvPUser(
        user_id=user_id,
        username=f"user{user_id}",
        display_name=f"User {user_id}",
    )


async def add_player(
    database: Database,
    *,
    user_id: int,
    season: str,
    rating: int,
    games: int,
) -> None:
    async with database.sessions.begin() as db:
        db.add(
            UserProfileRow(
                user_id=user_id,
                username=f"user{user_id}",
                display_name=f"User {user_id}",
            )
        )
        db.add(
            PvPPlayerRow(
                user_id=user_id,
                season=season,
                rating=rating,
                games=games,
                wins=games,
            )
        )


@pytest.mark.asyncio
async def test_placement_player_cannot_claim_rewards() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    repository = RankedRewardRepository(database.sessions)
    await database.create_all_for_tests()
    await add_player(
        database,
        user_id=1,
        season="season-1",
        rating=1200,
        games=4,
    )

    result = await repository.claim(user(1), "season-1")

    assert result.claimed_league_ids == ()
    assert result.gained_tokens == 0
    assert result.view.status.is_placement
    assert result.view.claimable_tokens == 0
    await database.close()


@pytest.mark.asyncio
async def test_claim_uses_peak_rating_and_is_idempotent() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    repository = RankedRewardRepository(database.sessions)
    await database.create_all_for_tests()
    await add_player(
        database,
        user_id=1,
        season="season-1",
        rating=1050,
        games=8,
    )
    async with database.sessions.begin() as db:
        db.add(UserProfileRow(user_id=2, display_name="Opponent"))
        started = datetime(2026, 8, 2, 8, tzinfo=UTC)
        db.add(
            PvPMatchRow(
                match_id="ranked-reward-peak",
                season="season-1",
                topic="Тестовая тема",
                pair_key="1:2",
                pro_user_id=1,
                con_user_id=2,
                winner_user_id=1,
                outcome="judged",
                rated=True,
                unrated_reason=None,
                pro_rating_before=1300,
                pro_rating_after=1320,
                con_rating_before=1000,
                con_rating_after=980,
                pro_scores={},
                con_scores={},
                reason="Победа",
                transcript=[],
                started_at=started,
                ended_at=started + timedelta(minutes=5),
            )
        )

    first = await repository.claim(user(1), "season-1")
    second = await repository.claim(user(1), "season-1")

    assert first.claimed_league_ids == (
        LeagueId.BRONZE,
        LeagueId.SILVER,
        LeagueId.GOLD,
        LeagueId.PLATINUM,
        LeagueId.DIAMOND,
        LeagueId.MASTER,
    )
    assert first.gained_tokens == 360
    assert first.wallet_tokens == 360
    assert first.view.peak_rating == 1320
    assert second.claimed_league_ids == ()
    assert second.gained_tokens == 0
    assert second.wallet_tokens == 360

    async with database.sessions() as db:
        claim_count = await db.scalar(
            select(func.count()).select_from(PvPRankedRewardClaimRow)
        )
        wallet = await db.get(
            PvPProgressionRow,
            {"user_id": 1, "season": "season-1"},
        )
    assert claim_count == 6
    assert wallet is not None
    assert wallet.tokens == 360
    await database.close()


@pytest.mark.asyncio
async def test_rewards_are_season_scoped_and_deletable() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    repository = RankedRewardRepository(database.sessions)
    await database.create_all_for_tests()
    await add_player(
        database,
        user_id=1,
        season="season-1",
        rating=1000,
        games=5,
    )
    async with database.sessions.begin() as db:
        db.add(
            PvPPlayerRow(
                user_id=1,
                season="season-2",
                rating=1100,
                games=5,
                wins=5,
            )
        )

    first = await repository.claim(user(1), "season-1")
    second = await repository.claim(user(1), "season-2")

    assert first.gained_tokens == 80
    assert second.gained_tokens == 140
    assert (await repository.view(1, "season-1")).wallet_tokens == 80
    assert (await repository.view(1, "season-2")).wallet_tokens == 140

    await repository.delete_user_data(1)
    async with database.sessions() as db:
        remaining = await db.scalar(
            select(func.count()).select_from(PvPRankedRewardClaimRow)
        )
    assert remaining == 0
    await database.close()
