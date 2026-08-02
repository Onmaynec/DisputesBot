from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .league_models import LeagueStatus


@dataclass(frozen=True, slots=True)
class CareerSeason:
    season: str
    rating: int
    starting_rating: int
    peak_rating: int
    rank: int
    games: int
    wins: int
    draws: int
    losses: int
    status: LeagueStatus
    last_activity: datetime

    @property
    def net_rating(self) -> int:
        return self.rating - self.starting_rating

    @property
    def win_rate(self) -> float:
        return 0.0 if self.games == 0 else self.wins * 100 / self.games


@dataclass(frozen=True, slots=True)
class CareerSummary:
    user_id: int
    display_name: str
    username: str | None
    seasons: tuple[CareerSeason, ...]
    total_games: int
    total_wins: int
    total_draws: int
    total_losses: int
    peak_rating: int

    @property
    def win_rate(self) -> float:
        return 0.0 if self.total_games == 0 else self.total_wins * 100 / self.total_games

    @property
    def best_season(self) -> CareerSeason:
        if not self.seasons:
            raise ValueError("career has no seasons")
        return max(
            self.seasons,
            key=lambda item: (item.rating, item.peak_rating, item.games, item.season),
        )


@dataclass(frozen=True, slots=True)
class SeasonArchiveStanding:
    rank: int
    user_id: int
    display_name: str
    username: str | None
    rating: int
    games: int
    wins: int
    draws: int
    losses: int
    status: LeagueStatus


@dataclass(frozen=True, slots=True)
class SeasonArchive:
    season: str
    total_players: int
    total_matches: int
    standings: tuple[SeasonArchiveStanding, ...]


@dataclass(frozen=True, slots=True)
class SeasonCatalogEntry:
    season: str
    players: int
    matches: int
    champion_user_id: int
    champion_name: str
    champion_username: str | None
    champion_rating: int
    champion_games: int
    champion_status: LeagueStatus
    last_activity: datetime
