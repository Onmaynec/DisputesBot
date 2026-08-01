from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from .cosmetics import CosmeticItem


class ProfileVisibility(StrEnum):
    PRIVATE = "private"
    PUBLIC = "public"


class ProfileLookupStatus(StrEnum):
    FOUND = "found"
    PRIVATE = "private"
    BLOCKED = "blocked"
    NOT_FOUND = "not_found"


@dataclass(frozen=True, slots=True)
class SocialProfileCard:
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
    is_public: bool


@dataclass(frozen=True, slots=True)
class ProfileLookupResult:
    status: ProfileLookupStatus
    profile: SocialProfileCard | None


@dataclass(frozen=True, slots=True)
class RivalSummary:
    opponent_id: int
    display_name: str
    username: str | None
    matches: int
    wins: int
    draws: int
    losses: int
    rated_matches: int
    rating_delta: int
    last_played_at: datetime


@dataclass(frozen=True, slots=True)
class HeadToHeadView:
    opponent_id: int
    display_name: str
    username: str | None
    season: str
    matches: int
    wins: int
    draws: int
    losses: int
    rated_matches: int
    rating_delta: int
    current_win_streak: int
    last_played_at: datetime
    recent_topics: tuple[str, ...]
