from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .league_models import LeagueStatus

SKILL_LABELS = {
    "logic": "логика",
    "evidence": "доказательства",
    "rebuttal": "опровержение",
}
SKILL_ORDER = ("logic", "evidence", "rebuttal")


@dataclass(frozen=True, slots=True)
class SeasonSkillAverages:
    logic: float
    evidence: float
    rebuttal: float
    scored_matches: int

    @property
    def total(self) -> float:
        return self.logic + self.evidence + self.rebuttal

    @property
    def strongest_key(self) -> str:
        values = self.as_dict()
        return max(SKILL_ORDER, key=lambda key: (values[key], -SKILL_ORDER.index(key)))

    @property
    def focus_key(self) -> str:
        values = self.as_dict()
        return min(SKILL_ORDER, key=lambda key: (values[key], SKILL_ORDER.index(key)))

    @property
    def strongest_label(self) -> str:
        return SKILL_LABELS[self.strongest_key]

    @property
    def focus_label(self) -> str:
        return SKILL_LABELS[self.focus_key]

    def as_dict(self) -> dict[str, float]:
        return {
            "logic": self.logic,
            "evidence": self.evidence,
            "rebuttal": self.rebuttal,
        }


@dataclass(frozen=True, slots=True)
class SeasonRecap:
    user_id: int
    season: str
    rating: int
    starting_rating: int
    peak_rating: int
    rank: int
    total_players: int
    games: int
    wins: int
    draws: int
    losses: int
    rated_matches: int
    unrated_matches: int
    unique_opponents: int
    longest_win_streak: int
    favorite_opponent_id: int | None
    favorite_opponent_name: str | None
    favorite_opponent_matches: int
    claimed_milestones: int
    claimed_tokens: int
    skills: SeasonSkillAverages | None
    status: LeagueStatus
    last_activity: datetime

    @property
    def net_rating(self) -> int:
        return self.rating - self.starting_rating

    @property
    def win_rate(self) -> float:
        return 0.0 if self.games == 0 else self.wins * 100 / self.games


@dataclass(frozen=True, slots=True)
class SeasonComparison:
    older: SeasonRecap
    newer: SeasonRecap

    @property
    def rating_delta(self) -> int:
        return self.newer.rating - self.older.rating

    @property
    def peak_delta(self) -> int:
        return self.newer.peak_rating - self.older.peak_rating

    @property
    def win_rate_delta(self) -> float:
        return self.newer.win_rate - self.older.win_rate

    @property
    def games_delta(self) -> int:
        return self.newer.games - self.older.games

    @property
    def streak_delta(self) -> int:
        return self.newer.longest_win_streak - self.older.longest_win_streak

    @property
    def skill_total_delta(self) -> float | None:
        if self.older.skills is None or self.newer.skills is None:
            return None
        return self.newer.skills.total - self.older.skills.total


@dataclass(frozen=True, slots=True)
class CareerRecords:
    user_id: int
    seasons: tuple[SeasonRecap, ...]
    highest_final: SeasonRecap
    highest_peak: SeasonRecap
    most_wins: SeasonRecap
    most_games: SeasonRecap
    best_win_rate: SeasonRecap
    biggest_gain: SeasonRecap
    longest_streak: SeasonRecap

    @property
    def seasons_count(self) -> int:
        return len(self.seasons)
