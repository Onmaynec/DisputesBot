from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class PersonalStreakRecord:
    wins: int
    season: str


@dataclass(frozen=True, slots=True)
class PersonalMatchRecord:
    season: str
    match_id: str
    opponent_user_id: int
    opponent_name: str
    value: float
    ended_at: datetime


@dataclass(frozen=True, slots=True)
class PersonalRivalRecord:
    opponent_user_id: int
    opponent_name: str
    matches: int
    last_match_at: datetime


@dataclass(frozen=True, slots=True)
class PvPRecordBook:
    user_id: int
    display_name: str
    seasons: int
    total_matches: int
    wins: int
    draws: int
    losses: int
    distinct_opponents: int
    longest_win_streak: PersonalStreakRecord | None
    best_rating_gain: PersonalMatchRecord | None
    biggest_upset: PersonalMatchRecord | None
    highest_score: PersonalMatchRecord | None
    favorite_rival: PersonalRivalRecord | None

    @property
    def win_rate(self) -> float:
        if self.total_matches == 0:
            return 0.0
        return self.wins * 100 / self.total_matches


@dataclass(frozen=True, slots=True)
class SeasonPlayerRecord:
    user_id: int
    display_name: str
    value: int
    rating: int
    games: int


@dataclass(frozen=True, slots=True)
class SeasonUpsetRecord:
    winner_user_id: int
    winner_name: str
    loser_user_id: int
    loser_name: str
    elo_gap: int
    ended_at: datetime
    match_id: str


@dataclass(frozen=True, slots=True)
class SeasonRivalryRecord:
    first_user_id: int
    first_name: str
    second_user_id: int
    second_name: str
    matches: int
    last_match_at: datetime


@dataclass(frozen=True, slots=True)
class SeasonRecordBook:
    season: str
    total_players: int
    total_matches: int
    most_wins: SeasonPlayerRecord | None
    most_games: SeasonPlayerRecord | None
    longest_win_streak: SeasonPlayerRecord | None
    biggest_upset: SeasonUpsetRecord | None
    busiest_rivalry: SeasonRivalryRecord | None
