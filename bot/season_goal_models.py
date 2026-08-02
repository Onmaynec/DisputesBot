from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from .league_models import LEAGUE_CATALOG, LeagueDefinition


class GoalMetric(StrEnum):
    ELO = "elo"
    LEAGUE = "league"
    WINS = "wins"
    MATCHES = "matches"
    WIN_RATE = "win_rate"
    STREAK = "streak"
    LOGIC = "logic"
    EVIDENCE = "evidence"
    REBUTTAL = "rebuttal"


@dataclass(frozen=True, slots=True)
class GoalDefinition:
    metric: GoalMetric
    label: str
    icon: str
    minimum: float
    maximum: float
    decimals: int
    minimum_samples: int
    aliases: tuple[str, ...]


GOAL_DEFINITIONS: tuple[GoalDefinition, ...] = (
    GoalDefinition(
        GoalMetric.ELO,
        "Elo",
        "📈",
        100,
        5_000,
        0,
        0,
        ("elo", "rating", "рейтинг"),
    ),
    GoalDefinition(
        GoalMetric.LEAGUE,
        "Лига",
        "🏆",
        0,
        1_450,
        0,
        5,
        ("league", "division", "лига", "дивизион"),
    ),
    GoalDefinition(
        GoalMetric.WINS,
        "Победы",
        "🏅",
        1,
        10_000,
        0,
        0,
        ("wins", "win", "победы", "побед"),
    ),
    GoalDefinition(
        GoalMetric.MATCHES,
        "Матчи",
        "⚔️",
        1,
        10_000,
        0,
        0,
        ("matches", "games", "матчи", "игры"),
    ),
    GoalDefinition(
        GoalMetric.WIN_RATE,
        "Win rate",
        "🎯",
        1,
        100,
        1,
        5,
        ("win_rate", "winrate", "wr", "процент", "винрейт"),
    ),
    GoalDefinition(
        GoalMetric.STREAK,
        "Серия побед",
        "🔥",
        1,
        1_000,
        0,
        0,
        ("streak", "win_streak", "серия", "стрик"),
    ),
    GoalDefinition(
        GoalMetric.LOGIC,
        "Логика",
        "🧠",
        0.1,
        10,
        1,
        3,
        ("logic", "логика"),
    ),
    GoalDefinition(
        GoalMetric.EVIDENCE,
        "Доказательства",
        "📚",
        0.1,
        10,
        1,
        3,
        ("evidence", "proof", "доказательства", "факты"),
    ),
    GoalDefinition(
        GoalMetric.REBUTTAL,
        "Опровержение",
        "🛡️",
        0.1,
        10,
        1,
        3,
        ("rebuttal", "опровержение", "контраргументы"),
    ),
)

_DEFINITION_BY_METRIC = {definition.metric: definition for definition in GOAL_DEFINITIONS}
_METRIC_ALIASES = {
    alias.casefold(): definition.metric
    for definition in GOAL_DEFINITIONS
    for alias in definition.aliases
}
_LEAGUE_ALIASES: dict[str, LeagueDefinition] = {}
for league in LEAGUE_CATALOG:
    aliases = {
        league.league_id.value,
        league.name.casefold(),
        league.name.casefold().replace("ё", "е"),
    }
    if league.league_id.value == "bronze":
        aliases.update(("бронза", "бронзе"))
    elif league.league_id.value == "silver":
        aliases.update(("серебро", "серебре"))
    elif league.league_id.value == "gold":
        aliases.update(("золото", "золоте"))
    elif league.league_id.value == "platinum":
        aliases.update(("платина", "платине"))
    elif league.league_id.value == "diamond":
        aliases.update(("алмаз", "алмазе"))
    elif league.league_id.value == "master":
        aliases.update(("мастер", "мастере"))
    elif league.league_id.value == "grandmaster":
        aliases.update(("грандмастер", "гм"))
    for alias in aliases:
        _LEAGUE_ALIASES[alias.casefold()] = league


class GoalInputError(ValueError):
    pass


class GoalLimitError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class MetricSnapshot:
    metric: GoalMetric
    value: float
    samples: int


@dataclass(frozen=True, slots=True)
class SeasonGoalView:
    metric: GoalMetric
    baseline_value: float
    target_value: float
    current_value: float
    samples: int
    completed_at: datetime | None
    created_at: datetime

    @property
    def definition(self) -> GoalDefinition:
        return definition_for(self.metric)

    @property
    def is_completed(self) -> bool:
        return self.completed_at is not None

    @property
    def progress(self) -> float:
        if self.is_completed:
            return 1.0
        span = self.target_value - self.baseline_value
        if span <= 0:
            return 1.0 if self.current_value >= self.target_value else 0.0
        return max(0.0, min(1.0, (self.current_value - self.baseline_value) / span))

    @property
    def progress_percent(self) -> int:
        return round(self.progress * 100)

    @property
    def sample_requirement_met(self) -> bool:
        return self.samples >= self.definition.minimum_samples


@dataclass(frozen=True, slots=True)
class GoalDashboard:
    user_id: int
    season: str
    goals: tuple[SeasonGoalView, ...]

    @property
    def active_count(self) -> int:
        return sum(not goal.is_completed for goal in self.goals)

    @property
    def completed_count(self) -> int:
        return sum(goal.is_completed for goal in self.goals)


@dataclass(frozen=True, slots=True)
class GoalSetResult:
    created: bool
    goal: SeasonGoalView


@dataclass(frozen=True, slots=True)
class GoalSuggestion:
    metric: GoalMetric
    target_value: float
    reason: str


def definition_for(metric: GoalMetric) -> GoalDefinition:
    return _DEFINITION_BY_METRIC[metric]


def parse_metric(raw: str) -> GoalMetric:
    normalized = raw.strip().casefold().replace("-", "_")
    metric = _METRIC_ALIASES.get(normalized)
    if metric is None:
        raise GoalInputError("Неизвестная метрика цели")
    return metric


def parse_target(metric: GoalMetric, raw: str) -> float:
    normalized = raw.strip().casefold().replace(",", ".")
    if metric is GoalMetric.LEAGUE:
        league = _LEAGUE_ALIASES.get(normalized.replace("ё", "е"))
        if league is None:
            raise GoalInputError("Неизвестная лига")
        return float(league.minimum_rating)

    try:
        value = float(normalized)
    except ValueError as exc:
        raise GoalInputError("Цель должна быть числом") from exc
    definition = definition_for(metric)
    if not definition.minimum <= value <= definition.maximum:
        raise GoalInputError(
            f"Допустимый диапазон: {format_number(definition.minimum, definition.decimals)}–"
            f"{format_number(definition.maximum, definition.decimals)}"
        )
    if definition.decimals == 0 and not value.is_integer():
        raise GoalInputError("Для этой метрики нужно целое число")
    return value


def league_for_target(target: float) -> LeagueDefinition:
    for league in LEAGUE_CATALOG:
        if league.minimum_rating == round(target):
            return league
    raise GoalInputError("Некорректная цель лиги")


def format_number(value: float, decimals: int) -> str:
    if decimals == 0:
        return str(round(value))
    return f"{value:.{decimals}f}"


def format_metric_value(metric: GoalMetric, value: float) -> str:
    if metric is GoalMetric.LEAGUE:
        league = league_for_target(value)
        return f"{league.icon} {league.name}"
    definition = definition_for(metric)
    rendered = format_number(value, definition.decimals)
    if metric is GoalMetric.WIN_RATE:
        return f"{rendered}%"
    if metric in {GoalMetric.LOGIC, GoalMetric.EVIDENCE, GoalMetric.REBUTTAL}:
        return f"{rendered}/10"
    return rendered
