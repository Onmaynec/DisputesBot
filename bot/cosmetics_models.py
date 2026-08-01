from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


@dataclass(frozen=True, slots=True)
class TitleDefinition:
    title_id: str
    name: str
    emoji: str
    description: str
    price_tokens: int
    minimum_points: int

    @property
    def label(self) -> str:
        return f"{self.emoji} {self.name}"


TITLE_CATALOG: tuple[TitleDefinition, ...] = (
    TitleDefinition(
        title_id="first_word",
        name="Первое слово",
        emoji="🗣️",
        description="Для тех, кто только начинает сезонный путь.",
        price_tokens=60,
        minimum_points=0,
    ),
    TitleDefinition(
        title_id="sharp_reply",
        name="Острое опровержение",
        emoji="⚡",
        description="Точный ответ без лишнего шума.",
        price_tokens=120,
        minimum_points=100,
    ),
    TitleDefinition(
        title_id="cold_logic",
        name="Хладнокровный логик",
        emoji="🧠",
        description="Аргументы прежде эмоций.",
        price_tokens=180,
        minimum_points=250,
    ),
    TitleDefinition(
        title_id="tactical_speaker",
        name="Тактический оратор",
        emoji="♟️",
        description="Каждый тезис занимает своё место.",
        price_tokens=260,
        minimum_points=450,
    ),
    TitleDefinition(
        title_id="argument_master",
        name="Мастер аргумента",
        emoji="🏛️",
        description="Структура, доказательства и сильное опровержение.",
        price_tokens=360,
        minimum_points=700,
    ),
    TitleDefinition(
        title_id="season_legend",
        name="Легенда сезона",
        emoji="👑",
        description="Редкий титул для вершины сезонного прогресса.",
        price_tokens=500,
        minimum_points=1_000,
    ),
)

_TITLE_BY_ID = {item.title_id: item for item in TITLE_CATALOG}


def title_by_id(title_id: str | None) -> TitleDefinition | None:
    if title_id is None:
        return None
    return _TITLE_BY_ID.get(title_id.strip().casefold())


@dataclass(frozen=True, slots=True)
class TitleShopEntry:
    definition: TitleDefinition
    owned: bool
    equipped: bool
    unlocked: bool


@dataclass(frozen=True, slots=True)
class TitleShopView:
    season: str
    tokens: int
    season_points: int
    entries: tuple[TitleShopEntry, ...]


@dataclass(frozen=True, slots=True)
class TitleInventoryView:
    season: str
    tokens: int
    owned: tuple[TitleDefinition, ...]
    equipped: TitleDefinition | None


class PurchaseOutcome(StrEnum):
    PURCHASED = "purchased"
    ALREADY_OWNED = "already_owned"
    INSUFFICIENT_TOKENS = "insufficient_tokens"
    LOCKED = "locked"
    UNKNOWN_TITLE = "unknown_title"


@dataclass(frozen=True, slots=True)
class TitlePurchaseResult:
    outcome: PurchaseOutcome
    definition: TitleDefinition | None
    tokens: int
    season_points: int
    auto_equipped: bool = False


class EquipOutcome(StrEnum):
    EQUIPPED = "equipped"
    ALREADY_EQUIPPED = "already_equipped"
    CLEARED = "cleared"
    NOT_OWNED = "not_owned"
    UNKNOWN_TITLE = "unknown_title"


@dataclass(frozen=True, slots=True)
class TitleEquipResult:
    outcome: EquipOutcome
    definition: TitleDefinition | None
