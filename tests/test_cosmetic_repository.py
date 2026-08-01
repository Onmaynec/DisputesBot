import importlib.util

import pytest

from bot.cosmetic_repository import CosmeticRepository
from bot.cosmetics import CosmeticKind, EquipStatus, PurchaseStatus
from bot.database import Database, PvPPlayerRow, PvPProgressionRow, UserProfileRow
from bot.pvp_models import PvPUser

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("aiosqlite") is None,
    reason="aiosqlite is not installed in the local sandbox",
)


async def make_player(
    database: Database,
    *,
    user_id: int = 1,
    tokens: int = 600,
    points: int = 700,
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
            PvPProgressionRow(
                user_id=user_id,
                season="season-1",
                tokens=tokens,
                season_points=points,
            )
        )
        db.add(
            PvPPlayerRow(
                user_id=user_id,
                season="season-1",
                rating=1042,
                games=4,
                wins=2,
                draws=1,
                losses=1,
            )
        )


@pytest.mark.asyncio
async def test_purchase_is_transactional_idempotent_and_auto_equips() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    repository = CosmeticRepository(database.sessions)
    await database.create_all_for_tests()
    await make_player(database)
    user = PvPUser(user_id=1, username="user1", display_name="User 1")

    first = await repository.purchase(user, "season-1", "sharp_mind")
    duplicate = await repository.purchase(user, "season-1", "sharp_mind")
    inventory = await repository.inventory(1, "season-1")

    assert first.status is PurchaseStatus.PURCHASED
    assert first.tokens == 480
    assert first.auto_equipped is True
    assert duplicate.status is PurchaseStatus.ALREADY_OWNED
    assert duplicate.tokens == 480
    assert inventory.owned_item_ids == frozenset({"sharp_mind"})
    assert inventory.equipped_title_id == "sharp_mind"
    await database.close()


@pytest.mark.asyncio
async def test_purchase_enforces_unlocks_and_balance() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    repository = CosmeticRepository(database.sessions)
    await database.create_all_for_tests()
    await make_player(database, tokens=100, points=100)
    user = PvPUser(user_id=1, display_name="User 1")

    locked = await repository.purchase(user, "season-1", "arena_legend")
    expensive = await repository.purchase(user, "season-1", "sharp_mind")
    missing = await repository.purchase(user, "season-1", "unknown")

    assert locked.status is PurchaseStatus.LOCKED
    assert expensive.status is PurchaseStatus.INSUFFICIENT_TOKENS
    assert missing.status is PurchaseStatus.UNKNOWN_ITEM
    inventory = await repository.inventory(1, "season-1")
    assert inventory.tokens == 100
    assert inventory.owned_item_ids == frozenset()
    await database.close()


@pytest.mark.asyncio
async def test_equip_profile_and_delete_inventory() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    repository = CosmeticRepository(database.sessions)
    await database.create_all_for_tests()
    await make_player(database)
    user = PvPUser(user_id=1, username="user1", display_name="User 1")

    await repository.purchase(user, "season-1", "spark")
    await repository.purchase(user, "season-1", "shield")
    equipped = await repository.equip(1, "season-1", "shield")
    not_owned = await repository.equip(1, "season-1", "steel_logic")
    profile = await repository.profile(user, "season-1")

    assert equipped.status is EquipStatus.EQUIPPED
    assert not_owned.status is EquipStatus.NOT_OWNED
    assert profile.badge is not None
    assert profile.badge.item_id == "shield"
    assert profile.rating == 1042
    assert profile.rank == 1
    assert (profile.games, profile.wins, profile.draws, profile.losses) == (4, 2, 1, 1)

    removed = await repository.unequip(1, "season-1", CosmeticKind.BADGE)
    assert removed.item is not None
    assert removed.item.item_id == "shield"
    await repository.delete_user_data(1)
    inventory = await repository.inventory(1, "season-1")
    assert inventory.owned_item_ids == frozenset()
    assert inventory.equipped_badge_id is None
    await database.close()
