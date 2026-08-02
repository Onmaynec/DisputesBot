from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


class SeasonPassInputError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class SeasonPassTier:
    tier_id: str
    name: str
    icon: str
    points_required: int
    reward_tokens: int


SEASON_PASS_TIERS: tuple[SeasonPassTier, ...] = (
    SeasonPassTier("rookie", "Новичок", "🌱", 100, 10),
    SeasonPassTier("contender", "Претендент", "🥉", 250, 15),
    SeasonPassTier("challenger", "Челленджер", "🥈", 500, 25),
    SeasonPassTier("veteran", "Ветеран", "🥇", 900, 35),
    SeasonPassTier("elite", "Элита", "💎", 1_400, 50),
    SeasonPassTier("champion", "Чемпион", "👑", 2_000, 70),
    SeasonPassTier("legend", "Легенда", "🏆", 3_000, 100),
)

_TIER_BY_ID = {tier.tier_id: tier for tier in SEASON_PASS_TIERS}


@dataclass(frozen=True, slots=True)
class SeasonPassTierView:
    tier: SeasonPassTier
    season_points: int
    claimed_at: datetime | None

    @property
    def is_unlocked(self) -> bool:
        return self.season_points >= self.tier.points_required

    @property
    def is_claimed(self) -> bool:
        return self.claimed_at is not None

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

    @property
    def claimable_count(self) -> int:
        return sum(tier.is_claimable for tier in self.tiers)

    @property
    def claimed_count(self) -> int:
        return sum(tier.is_claimed for tier in self.tiers)

    @property
    def next_tier(self) -> SeasonPassTierView | None:
        return next((tier for tier in self.tiers if not tier.is_unlocked), None)


@dataclass(frozen=True, slots=True)
class SeasonPassClaimResult:
    claimed_tier_ids: tuple[str, ...]
    gained_tokens: int
    wallet_tokens: int
    season_points: int


def tier_for_id(tier_id: str) -> SeasonPassTier:
    try:
        return _TIER_BY_ID[tier_id]
    except KeyError as exc:
        raise SeasonPassInputError("Неизвестный уровень сезонного пропуска") from exc
