import importlib.util

import pytest

from bot.cosmetics_models import EquipOutcome, PurchaseOutcome
from bot.cosmetics_repository import CosmeticsRepository
from bot.database import Database, PvPProgressionRow, UserProfileRow
from bot.pvp_models import PvPUser

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("aiosqlite") is None,
    reason="aiosqlite is not installed in the local sandbox",
)


async def seeded_repository() -> tuple[Database, CosmeticsRepository]:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_all_for_tests()
    async with database.sessions.begin() as db:
        db.add(UserProfileRow(user_id=1, display_name="User 1"))
        db.add(
            PvPProgressionRow(
                user_id=1,
                season="season-1",
                tokens=700,
                season_points=800,
            )
        )
    return database, CosmeticsRepository(database.sessions)


@pytest.mark.asyncio
async def test_purchase_is_idempotent_and_first_title_is_auto_equipped() -> None:
    database, repository = await seeded_repository()
    user = PvPUser(user_id=1, display_name="User 1")

    first = await repository.purchase(user, "season-1", "sharp_reply")
    duplicate = await repository.purchase(user, "season-1", "sharp_reply")
    inventory = await repository.inventory(1, "season-1")

    assert first.outcome == PurchaseOutcome.PURCHASED
    assert first.auto_equipped is True
    assert first.tokens == 580
    assert duplicate.outcome == PurchaseOutcome.ALREADY_OWNED
    assert duplicate.tokens == 580
    assert [item.title_id for item in inventory.owned] == ["sharp_reply"]
    assert inventory.equipped is not None
    assert inventory.equipped.title_id == "sharp_reply"
    await database.close()


@pytest.mark.asyncio
async def test_locked_and_insufficient_purchases_do_not_spend_tokens() -> None:
    database, repository = await seeded_repository()
    user = PvPUser(user_id=1, display_name="User 1")

    locked = await repository.purchase(user, "season-1", "season_legend")
    async with database.sessions.begin() as db:
        wallet = await db.get(
            PvPProgressionRow,
            {"user_id": 1, "season": "season-1"},
        )
        wallet.season_points = 1_000
        wallet.tokens = 100
    insufficient = await repository.purchase(user, "season-1", "season_legend")

    assert locked.outcome == PurchaseOutcome.LOCKED
    assert locked.tokens == 700
    assert insufficient.outcome == PurchaseOutcome.INSUFFICIENT_TOKENS
    assert insufficient.tokens == 100
    await database.close()


@pytest.mark.asyncio
async def test_equip_requires_ownership_and_can_be_cleared() -> None:
    database, repository = await seeded_repository()
    user = PvPUser(user_id=1, display_name="User 1")

    missing = await repository.equip(1, "season-1", "cold_logic")
    await repository.purchase(user, "season-1", "sharp_reply")
    await repository.purchase(user, "season-1", "cold_logic")
    equipped = await repository.equip(1, "season-1", "cold_logic")
    repeated = await repository.equip(1, "season-1", "cold_logic")
    cleared = await repository.equip(1, "season-1", "none")
    inventory = await repository.inventory(1, "season-1")

    assert missing.outcome == EquipOutcome.NOT_OWNED
    assert equipped.outcome == EquipOutcome.EQUIPPED
    assert repeated.outcome == EquipOutcome.ALREADY_EQUIPPED
    assert cleared.outcome == EquipOutcome.CLEARED
    assert inventory.equipped is None
    assert {item.title_id for item in inventory.owned} == {"sharp_reply", "cold_logic"}
    await database.close()
