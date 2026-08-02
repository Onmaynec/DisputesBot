import importlib.util
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from bot.cosmetic_database import PvPCosmeticLoadoutRow, PvPCosmeticRow
from bot.database import Database, PvPProgressionRow, UserProfileRow
from bot.pvp_models import PvPUser
from bot.season_pass_database import PvPSeasonPassClaimRow
from bot.season_pass_models import SEASON_PASS_TIERS
from bot.season_pass_repository import SeasonPassRepository

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("aiosqlite") is None,
    reason="aiosqlite is not installed in the local sandbox",
)

USER = PvPUser(user_id=1, username="user1", display_name="User 1")


async def database_with_wallet(points: int, tokens: int = 0) -> Database:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_all_for_tests()
    async with database.sessions.begin() as db:
        db.add(UserProfileRow(user_id=1, username="user1", display_name="User 1"))
        db.add(
            PvPProgressionRow(
                user_id=1,
                season="season-1",
                season_points=points,
                tokens=tokens,
            )
        )
    return database


@pytest.mark.asyncio
async def test_claim_grants_items_and_auto_equips_empty_slots() -> None:
    database = await database_with_wallet(550, 5)
    result = await SeasonPassRepository(database.sessions).claim(USER, "season-1")

    assert result.claimed_tier_ids == ("rookie", "contender", "challenger")
    assert result.granted_cosmetic_ids == (
        "pass_rookie_leaf",
        "pass_contender_voice",
        "pass_challenger_quill",
    )
    assert result.auto_equipped_ids == ("pass_rookie_leaf", "pass_contender_voice")
    assert result.gained_tokens == 50

    async with database.sessions() as db:
        item_ids = set(
            await db.scalars(
                select(PvPCosmeticRow.item_id).where(PvPCosmeticRow.user_id == 1)
            )
        )
        loadout = await db.get(
            PvPCosmeticLoadoutRow,
            {"user_id": 1, "season": "season-1"},
        )
        claims = list(await db.scalars(select(PvPSeasonPassClaimRow)))
    assert item_ids == set(result.granted_cosmetic_ids)
    assert loadout is not None
    assert loadout.badge_id == "pass_rookie_leaf"
    assert loadout.title_id == "pass_contender_voice"
    assert all(row.reward_item_id for row in claims)
    assert all(row.cosmetic_granted_at for row in claims)
    await database.close()


@pytest.mark.asyncio
async def test_v020_claim_backfills_item_without_repaying_tokens() -> None:
    database = await database_with_wallet(100, 10)
    claimed_at = datetime(2026, 8, 2, tzinfo=UTC)
    async with database.sessions.begin() as db:
        db.add(
            PvPSeasonPassClaimRow(
                user_id=1,
                season="season-1",
                tier_id="rookie",
                points_required=100,
                reward_tokens=10,
                claimed_points=100,
                claimed_at=claimed_at,
            )
        )

    result = await SeasonPassRepository(database.sessions).claim(USER, "season-1")

    assert result.claimed_tier_ids == ()
    assert result.gained_tokens == 0
    assert result.wallet_tokens == 10
    assert result.granted_cosmetic_ids == ("pass_rookie_leaf",)
    async with database.sessions() as db:
        row = await db.get(
            PvPSeasonPassClaimRow,
            {"user_id": 1, "season": "season-1", "tier_id": "rookie"},
        )
    assert row is not None
    persisted_claimed_at = row.claimed_at
    if persisted_claimed_at.tzinfo is None:
        persisted_claimed_at = persisted_claimed_at.replace(tzinfo=UTC)
    assert persisted_claimed_at == claimed_at
    assert row.reward_item_id == "pass_rookie_leaf"
    assert row.cosmetic_granted_at is not None
    await database.close()


def test_each_tier_has_a_unique_known_cosmetic() -> None:
    item_ids = [tier.reward_cosmetic_id for tier in SEASON_PASS_TIERS]
    assert len(item_ids) == len(set(item_ids))
    assert all(
        tier.reward_cosmetic.item_id == tier.reward_cosmetic_id
        for tier in SEASON_PASS_TIERS
    )
