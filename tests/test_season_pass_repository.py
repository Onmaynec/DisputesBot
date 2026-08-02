import importlib.util

import pytest
from sqlalchemy import select

from bot.database import Database, PvPProgressionRow, UserProfileRow
from bot.pvp_models import PvPUser
from bot.season_pass_database import PvPSeasonPassClaimRow
from bot.season_pass_models import SEASON_PASS_TIERS, SeasonPassInputError
from bot.season_pass_repository import SeasonPassRepository

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("aiosqlite") is None,
    reason="aiosqlite is not installed in the local sandbox",
)


USER = PvPUser(user_id=1, username="user1", display_name="User 1")


async def create_database(*, points: int = 0, tokens: int = 0) -> Database:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_all_for_tests()
    async with database.sessions.begin() as db:
        db.add(UserProfileRow(user_id=1, username="user1", display_name="User 1"))
        db.add(
            PvPProgressionRow(
                user_id=1,
                season="season-1",
                tokens=tokens,
                season_points=points,
            )
        )
    return database


@pytest.mark.asyncio
async def test_dashboard_shows_progress_and_next_tier() -> None:
    database = await create_database(points=180, tokens=7)
    repository = SeasonPassRepository(database.sessions)

    dashboard = await repository.dashboard(1, "season-1")

    assert dashboard.season_points == 180
    assert dashboard.wallet_tokens == 7
    assert dashboard.claimable_count == 1
    assert dashboard.claimed_count == 0
    assert dashboard.tiers[0].is_claimable is True
    assert dashboard.next_tier is not None
    assert dashboard.next_tier.tier.tier_id == "contender"
    assert dashboard.next_tier.progress_percent == 72
    await database.close()


@pytest.mark.asyncio
async def test_claims_all_unlocked_tiers_once_and_updates_wallet() -> None:
    database = await create_database(points=550, tokens=5)
    repository = SeasonPassRepository(database.sessions)

    first = await repository.claim(USER, "season-1")

    assert first.claimed_tier_ids == ("rookie", "contender", "challenger")
    assert first.gained_tokens == 50
    assert first.wallet_tokens == 55
    assert first.season_points == 550

    second = await repository.claim(USER, "season-1")
    assert second.claimed_tier_ids == ()
    assert second.gained_tokens == 0
    assert second.wallet_tokens == 55
    assert second.season_points == 550

    async with database.sessions() as db:
        rows = list(
            await db.scalars(
                select(PvPSeasonPassClaimRow)
                .where(
                    PvPSeasonPassClaimRow.user_id == 1,
                    PvPSeasonPassClaimRow.season == "season-1",
                )
                .order_by(PvPSeasonPassClaimRow.points_required.asc())
            )
        )
        wallet = await db.get(
            PvPProgressionRow,
            {"user_id": 1, "season": "season-1"},
        )
    assert [row.tier_id for row in rows] == ["rookie", "contender", "challenger"]
    assert all(row.claimed_points == 550 for row in rows)
    assert wallet is not None
    assert wallet.tokens == 55
    assert wallet.season_points == 550
    await database.close()


@pytest.mark.asyncio
async def test_later_points_claim_only_newly_unlocked_tiers() -> None:
    database = await create_database(points=100)
    repository = SeasonPassRepository(database.sessions)

    first = await repository.claim(USER, "season-1")
    assert first.claimed_tier_ids == ("rookie",)
    assert first.wallet_tokens == 10

    async with database.sessions.begin() as db:
        wallet = await db.get(
            PvPProgressionRow,
            {"user_id": 1, "season": "season-1"},
        )
        assert wallet is not None
        wallet.season_points = 900

    second = await repository.claim(USER, "season-1")
    assert second.claimed_tier_ids == ("contender", "challenger", "veteran")
    assert second.gained_tokens == 75
    assert second.wallet_tokens == 85
    assert second.season_points == 900
    await database.close()


@pytest.mark.asyncio
async def test_seasons_are_isolated() -> None:
    database = await create_database(points=250)
    repository = SeasonPassRepository(database.sessions)
    first = await repository.claim(USER, "season-1")
    assert first.claimed_tier_ids == ("rookie", "contender")

    async with database.sessions.begin() as db:
        db.add(
            PvPProgressionRow(
                user_id=1,
                season="season-2",
                tokens=0,
                season_points=100,
            )
        )

    next_season = await repository.claim(USER, "season-2")
    assert next_season.claimed_tier_ids == ("rookie",)
    assert next_season.wallet_tokens == 10

    dashboard = await repository.dashboard(1, "season-1")
    assert dashboard.claimed_count == 2
    assert dashboard.wallet_tokens == 25
    await database.close()


@pytest.mark.asyncio
async def test_claim_creates_empty_wallet_and_rejects_invalid_season() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_all_for_tests()
    repository = SeasonPassRepository(database.sessions)

    result = await repository.claim(USER, "season-1")
    assert result.claimed_tier_ids == ()
    assert result.wallet_tokens == 0
    assert result.season_points == 0

    with pytest.raises(SeasonPassInputError):
        await repository.dashboard(1, "")
    with pytest.raises(SeasonPassInputError):
        await repository.claim(USER, "x" * 33)
    await database.close()


@pytest.mark.asyncio
async def test_delete_user_data_removes_claim_rows() -> None:
    database = await create_database(points=100)
    repository = SeasonPassRepository(database.sessions)
    await repository.claim(USER, "season-1")

    await repository.delete_user_data(1)
    async with database.sessions() as db:
        rows = list(
            await db.scalars(
                select(PvPSeasonPassClaimRow).where(
                    PvPSeasonPassClaimRow.user_id == 1
                )
            )
        )
    assert rows == []
    await database.close()


def test_catalog_is_ordered_unique_and_non_circular() -> None:
    points = [tier.points_required for tier in SEASON_PASS_TIERS]
    ids = [tier.tier_id for tier in SEASON_PASS_TIERS]
    assert points == sorted(points)
    assert len(ids) == len(set(ids))
    assert all(tier.reward_tokens > 0 for tier in SEASON_PASS_TIERS)
    assert SEASON_PASS_TIERS[-1].points_required == 3_000
