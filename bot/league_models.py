from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

DEFAULT_PLACEMENT_GAMES = 5


class LeagueId(StrEnum):
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    PLATINUM = "platinum"
    DIAMOND = "diamond"
    MASTER = "master"
    GRANDMASTER = "grandmaster"


@dataclass(frozen=True, slots=True)
class LeagueDefinition:
    league_id: LeagueId
    name: str
    icon: str
    minimum_rating: int
    next_minimum_rating: int | None

    def progress_text(self, rating: int) -> str:
        if self.next_minimum_rating is None:
            return "максимальный дивизион"
        gained = max(0, rating - self.minimum_rating)
        required = self.next_minimum_rating - self.minimum_rating
        return f"{min(gained, required)}/{required}"

    def rating_to_next(self, rating: int) -> int:
        if self.next_minimum_rating is None:
            return 0
        return max(0, self.next_minimum_rating - rating)


LEAGUE_CATALOG: tuple[LeagueDefinition, ...] = (
    LeagueDefinition(LeagueId.BRONZE, "Бронза", "🥉", 0, 900),
    LeagueDefinition(LeagueId.SILVER, "Серебро", "🥈", 900, 1_000),
    LeagueDefinition(LeagueId.GOLD, "Золото", "🥇", 1_000, 1_100),
    LeagueDefinition(LeagueId.PLATINUM, "Платина", "💠", 1_100, 1_200),
    LeagueDefinition(LeagueId.DIAMOND, "Алмаз", "💎", 1_200, 1_300),
    LeagueDefinition(LeagueId.MASTER, "Мастер", "🏅", 1_300, 1_450),
    LeagueDefinition(LeagueId.GRANDMASTER, "Грандмастер", "👑", 1_450, None),
)


@dataclass(frozen=True, slots=True)
class LeagueStatus:
    rating: int
    games: int
    placement_games: int
    league: LeagueDefinition | None

    @property
    def is_placement(self) -> bool:
        return self.league is None

    @property
    def placement_remaining(self) -> int:
        return max(0, self.placement_games - self.games)

    @property
    def icon(self) -> str:
        return "🧭" if self.league is None else self.league.icon

    @property
    def name(self) -> str:
        return "Калибровка" if self.league is None else self.league.name


@dataclass(frozen=True, slots=True)
class LeaguePlayerView:
    user_id: int
    display_name: str
    username: str | None
    season: str
    rating: int
    rank: int
    games: int
    wins: int
    draws: int
    losses: int
    status: LeagueStatus
    recent_rating_delta: int
    recent_form: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LeagueStanding:
    user_id: int
    display_name: str
    username: str | None
    rating: int
    games: int
    status: LeagueStatus


@dataclass(frozen=True, slots=True)
class LeagueDistributionEntry:
    key: str
    name: str
    icon: str
    players: int


@dataclass(frozen=True, slots=True)
class LeagueDistribution:
    season: str
    total_players: int
    entries: tuple[LeagueDistributionEntry, ...]


def league_for_rating(rating: int) -> LeagueDefinition:
    normalized = max(0, rating)
    selected = LEAGUE_CATALOG[0]
    for definition in LEAGUE_CATALOG:
        if normalized >= definition.minimum_rating:
            selected = definition
        else:
            break
    return selected


def league_status(
    rating: int,
    games: int,
    *,
    placement_games: int = DEFAULT_PLACEMENT_GAMES,
) -> LeagueStatus:
    if placement_games < 0:
        raise ValueError("placement_games must not be negative")
    normalized_games = max(0, games)
    league = None if normalized_games < placement_games else league_for_rating(rating)
    return LeagueStatus(
        rating=rating,
        games=normalized_games,
        placement_games=placement_games,
        league=league,
    )
