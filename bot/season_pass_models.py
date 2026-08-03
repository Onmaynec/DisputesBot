from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .cosmetics import (
    SEASON_PASS_COMPLETION_COSMETIC,
    CosmeticItem,
    season_pass_cosmetic_by_id,
)


class SeasonPassInputError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class SeasonPassTier:
    tier_id: str
    name: str
    icon: str
    points_required: int
    reward_tokens: int
    reward_cosmetic_id: str

    @property
    def reward_cosmetic(self) -> CosmeticItem:
        item = season_pass_cosmetic_by_id(self.reward_cosmetic_id)
        if item is None:
            raise SeasonPassInputError("Уровень ссылается на неизвестную косметику")
        return item


SEASON_PASS_TIERS: tuple[SeasonPassTier, ...] = (
    SeasonPassTier("rookie", "Новичок", "🌱", 100, 10, "pass_rookie_leaf"),
    SeasonPassTier(
        "contender",
        "Претендент",
        "🥉",
        250,
        15,
        "pass_contender_voice",
    ),
    SeasonPassTier(
        "challenger",
        "Челленджер",
        "🥈",
        500,
        25,
        "pass_challenger_quill",
    ),
    SeasonPassTier("veteran", "Ветеран", "🥇", 900, 35, "pass_veteran"),
    SeasonPassTier(
        "elite",
        "Элита",
        "💎",
        1_400,
        50,
        "pass_elite_crystal",
    ),
    SeasonPassTier(
        "champion",
        "Чемпион",
        "👑",
        2_000,
        70,
        "pass_champion",
    ),
    SeasonPassTier(
        "legend",
        "Легенда",
        "🏆",
        3_000,
        100,
        "pass_legend_trophy",
    ),
)

_TIER_BY_ID = {tier.tier_id: tier for tier in SEASON_PASS_TIERS}


@dataclass(frozen=True, slots=True)
class SeasonPassTierView:
    tier: SeasonPassTier
    season_points: int
    claimed_at: datetime | None
    cosmetic_granted_at: datetime | None

    @property
    def is_unlocked(self) -> bool:
        return self.season_points >= self.tier.points_required

    @property
    def token_claimed(self) -> bool:
        return self.claimed_at is not None

    @property
    def cosmetic_granted(self) -> bool:
        return self.cosmetic_granted_at is not None

    @property
    def is_claimed(self) -> bool:
        return self.token_claimed and self.cosmetic_granted

    @property
    def is_claimable(self) -> bool:
        return self.is_unlocked and not self.is_claimed

    @property
    def progress(self) -> float:
        if self.tier.points_required <= 0:
            return 1.0
        return max(0.0, min(1.0, self.season_points / self.tier.points_required))

    @property
    def progress_percent(self) -> int:
        return round(self.progress * 100)


@dataclass(frozen=True, slots=True)
class SeasonPassDashboard:
    user_id: int
    season: str
    season_points: int
    wallet_tokens: int
    tiers: tuple[SeasonPassTierView, ...]
    completion_cosmetic_owned: bool = False

    @property
    def completion_cosmetic(self) -> CosmeticItem:
        return SEASON_PASS_COMPLETION_COSMETIC

    @property
    def all_tiers_claimed(self) -> bool:
        return bool(self.tiers) and all(tier.is_claimed for tier in self.tiers)

    @property
    def completion_reward_claimable(self) -> bool:
        return self.all_tiers_claimed and not self.completion_cosmetic_owned

    @property
    def claimable_count(self) -> int:
        return sum(tier.is_claimable for tier in self.tiers) + int(
            self.completion_reward_claimable
        )

    @property
    def claimed_count(self) -> int:
        return sum(tier.is_claimed for tier in self.tiers)

    @property
    def collection_count(self) -> int:
        return self.claimed_count + int(self.completion_cosmetic_owned)

    @property
    def collection_total(self) -> int:
        return len(self.tiers) + 1

    @property
    def next_tier(self) -> SeasonPassTierView | None:
        return next((tier for tier in self.tiers if not tier.is_unlocked), None)


@dataclass(frozen=True, slots=True)
class SeasonPassClaimResult:
    claimed_tier_ids: tuple[str, ...]
    granted_cosmetic_ids: tuple[str, ...]
    auto_equipped_ids: tuple[str, ...]
    gained_tokens: int
    wallet_tokens: int
    season_points: int

    @property
    def changed(self) -> bool:
        return bool(self.claimed_tier_ids or self.granted_cosmetic_ids)


def tier_for_id(tier_id: str) -> SeasonPassTier:
    try:
        return _TIER_BY_ID[tier_id]
    except KeyError as exc:
        raise SeasonPassInputError("Неизвестный уровень сезонного пропуска") from exc
