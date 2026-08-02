from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CosmeticKind(StrEnum):
    TITLE = "title"
    BADGE = "badge"


class PurchaseStatus(StrEnum):
    PURCHASED = "purchased"
    ALREADY_OWNED = "already_owned"
    LOCKED = "locked"
    INSUFFICIENT_TOKENS = "insufficient_tokens"
    UNKNOWN_ITEM = "unknown_item"


class EquipStatus(StrEnum):
    EQUIPPED = "equipped"
    NOT_OWNED = "not_owned"
    UNKNOWN_ITEM = "unknown_item"
    EMPTY_INVENTORY = "empty_inventory"


@dataclass(frozen=True, slots=True)
class CosmeticItem:
    item_id: str
    kind: CosmeticKind
    name: str
    display: str
    price_tokens: int
    required_points: int = 0


@dataclass(frozen=True, slots=True)
class CosmeticInventoryView:
    season: str
    tokens: int
    season_points: int
    owned_item_ids: frozenset[str]
    equipped_title_id: str | None
    equipped_badge_id: str | None


@dataclass(frozen=True, slots=True)
class PurchaseResult:
    status: PurchaseStatus
    item: CosmeticItem | None
    tokens: int
    season_points: int
    auto_equipped: bool = False


@dataclass(frozen=True, slots=True)
class EquipResult:
    status: EquipStatus
    item: CosmeticItem | None


@dataclass(frozen=True, slots=True)
class PvPProfileCard:
    user_id: int
    display_name: str
    username: str | None
    season: str
    rating: int | None
    rank: int | None
    games: int
    wins: int
    draws: int
    losses: int
    season_points: int
    tokens: int
    title: CosmeticItem | None
    badge: CosmeticItem | None


SHOP_COSMETIC_CATALOG: tuple[CosmeticItem, ...] = (
    CosmeticItem("spark", CosmeticKind.BADGE, "Искра", "⚡", 80),
    CosmeticItem("shield", CosmeticKind.BADGE, "Щит аргументов", "🛡️", 160, 100),
    CosmeticItem("crown", CosmeticKind.BADGE, "Корона оратора", "👑", 320, 450),
    CosmeticItem("phoenix", CosmeticKind.BADGE, "Феникс серии", "🔥", 500, 700),
    CosmeticItem("sharp_mind", CosmeticKind.TITLE, "Острый ум", "Острый ум", 120, 100),
    CosmeticItem(
        "steel_logic",
        CosmeticKind.TITLE,
        "Стальная логика",
        "Стальная логика",
        220,
        250,
    ),
    CosmeticItem(
        "master_rebuttal",
        CosmeticKind.TITLE,
        "Мастер опровержения",
        "Мастер опровержения",
        350,
        450,
    ),
    CosmeticItem(
        "arena_legend",
        CosmeticKind.TITLE,
        "Легенда арены",
        "Легенда арены",
        550,
        1_000,
    ),
)

# Larger than PostgreSQL INTEGER can hold, so these items cannot be purchased through
# the legacy /buy path. They are granted only by the season-pass transaction.
_REWARD_ONLY_PRICE = 2_147_483_648

SEASON_PASS_COSMETIC_CATALOG: tuple[CosmeticItem, ...] = (
    CosmeticItem(
        "pass_rookie_leaf",
        CosmeticKind.BADGE,
        "Росток сезона",
        "🌿",
        _REWARD_ONLY_PRICE,
    ),
    CosmeticItem(
        "pass_contender_voice",
        CosmeticKind.TITLE,
        "Восходящий голос",
        "Восходящий голос",
        _REWARD_ONLY_PRICE,
    ),
    CosmeticItem(
        "pass_challenger_quill",
        CosmeticKind.BADGE,
        "Серебряное перо",
        "🪶",
        _REWARD_ONLY_PRICE,
    ),
    CosmeticItem(
        "pass_veteran",
        CosmeticKind.TITLE,
        "Ветеран пропуска",
        "Ветеран пропуска",
        _REWARD_ONLY_PRICE,
    ),
    CosmeticItem(
        "pass_elite_crystal",
        CosmeticKind.BADGE,
        "Кристалл аргумента",
        "🔷",
        _REWARD_ONLY_PRICE,
    ),
    CosmeticItem(
        "pass_champion",
        CosmeticKind.TITLE,
        "Чемпион сезона",
        "Чемпион сезона",
        _REWARD_ONLY_PRICE,
    ),
    CosmeticItem(
        "pass_legend_trophy",
        CosmeticKind.BADGE,
        "Трофей легенды",
        "🏆",
        _REWARD_ONLY_PRICE,
    ),
)

# Backward-compatible name for the paid shop catalog.
COSMETIC_CATALOG = SHOP_COSMETIC_CATALOG
ALL_COSMETIC_CATALOG = SHOP_COSMETIC_CATALOG + SEASON_PASS_COSMETIC_CATALOG

_COSMETICS_BY_ID = {item.item_id: item for item in ALL_COSMETIC_CATALOG}
_SHOP_COSMETICS_BY_ID = {item.item_id: item for item in SHOP_COSMETIC_CATALOG}
_SEASON_PASS_COSMETICS_BY_ID = {
    item.item_id: item for item in SEASON_PASS_COSMETIC_CATALOG
}


def cosmetic_by_id(item_id: str | None) -> CosmeticItem | None:
    if item_id is None:
        return None
    return _COSMETICS_BY_ID.get(item_id.strip().lower())


def shop_cosmetic_by_id(item_id: str | None) -> CosmeticItem | None:
    if item_id is None:
        return None
    return _SHOP_COSMETICS_BY_ID.get(item_id.strip().lower())


def season_pass_cosmetic_by_id(item_id: str | None) -> CosmeticItem | None:
    if item_id is None:
        return None
    return _SEASON_PASS_COSMETICS_BY_ID.get(item_id.strip().lower())


def cosmetics_by_kind(
    kind: CosmeticKind,
    *,
    include_season_pass: bool = False,
) -> tuple[CosmeticItem, ...]:
    catalog = ALL_COSMETIC_CATALOG if include_season_pass else SHOP_COSMETIC_CATALOG
    return tuple(item for item in catalog if item.kind is kind)
