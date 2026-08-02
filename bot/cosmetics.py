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
    CosmeticItem(
        item_id="spark",
        kind=CosmeticKind.BADGE,
        name="Искра",
        display="⚡",
        price_tokens=80,
    ),
    CosmeticItem(
        item_id="shield",
        kind=CosmeticKind.BADGE,
        name="Щит аргументов",
        display="🛡️",
        price_tokens=160,
        required_points=100,
    ),
    CosmeticItem(
        item_id="crown",
        kind=CosmeticKind.BADGE,
        name="Корона оратора",
        display="👑",
        price_tokens=320,
        required_points=450,
    ),
    CosmeticItem(
        item_id="phoenix",
        kind=CosmeticKind.BADGE,
        name="Феникс серии",
        display="🔥",
        price_tokens=500,
        required_points=700,
    ),
    CosmeticItem(
        item_id="sharp_mind",
        kind=CosmeticKind.TITLE,
        name="Острый ум",
        display="Острый ум",
        price_tokens=120,
        required_points=100,
    ),
    CosmeticItem(
        item_id="steel_logic",
        kind=CosmeticKind.TITLE,
        name="Стальная логика",
        display="Стальная логика",
        price_tokens=220,
        required_points=250,
    ),
    CosmeticItem(
        item_id="master_rebuttal",
        kind=CosmeticKind.TITLE,
        name="Мастер опровержения",
        display="Мастер опровержения",
        price_tokens=350,
        required_points=450,
    ),
    CosmeticItem(
        item_id="arena_legend",
        kind=CosmeticKind.TITLE,
        name="Легенда арены",
        display="Легенда арены",
        price_tokens=550,
        required_points=1_000,
    ),
)

SEASON_PASS_COSMETIC_CATALOG: tuple[CosmeticItem, ...] = (
    CosmeticItem(
        item_id="pass_rookie_leaf",
        kind=CosmeticKind.BADGE,
        name="Росток сезона",
        display="🌿",
        price_tokens=0,
    ),
    CosmeticItem(
        item_id="pass_contender_voice",
        kind=CosmeticKind.TITLE,
        name="Восходящий голос",
        display="Восходящий голос",
        price_tokens=0,
    ),
    CosmeticItem(
        item_id="pass_challenger_quill",
        kind=CosmeticKind.BADGE,
        name="Серебряное перо",
        display="🪶",
        price_tokens=0,
    ),
    CosmeticItem(
        item_id="pass_veteran",
        kind=CosmeticKind.TITLE,
        name="Ветеран пропуска",
        display="Ветеран пропуска",
        price_tokens=0,
    ),
    CosmeticItem(
        item_id="pass_elite_crystal",
        kind=CosmeticKind.BADGE,
        name="Кристалл аргумента",
        display="🔷",
        price_tokens=0,
    ),
    CosmeticItem(
        item_id="pass_champion",
        kind=CosmeticKind.TITLE,
        name="Чемпион сезона",
        display="Чемпион сезона",
        price_tokens=0,
    ),
    CosmeticItem(
        item_id="pass_legend_trophy",
        kind=CosmeticKind.BADGE,
        name="Трофей легенды",
        display="🏆",
        price_tokens=0,
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
