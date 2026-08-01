from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from hashlib import sha256


class DailyQuestKind(StrEnum):
    PLAY_MATCHES = "play_matches"
    WIN_MATCHES = "win_matches"
    RATED_MATCHES = "rated_matches"
    UNIQUE_OPPONENTS = "unique_opponents"
    RATED_WINS = "rated_wins"


@dataclass(frozen=True, slots=True)
class DailyQuestDefinition:
    quest_id: str
    kind: DailyQuestKind
    title: str
    target: int
    reward_tokens: int
    reward_points: int


DAILY_QUEST_CATALOG: tuple[DailyQuestDefinition, ...] = (
    DailyQuestDefinition(
        quest_id="play_1",
        kind=DailyQuestKind.PLAY_MATCHES,
        title="Завершить 1 PvP-матч",
        target=1,
        reward_tokens=20,
        reward_points=20,
    ),
    DailyQuestDefinition(
        quest_id="play_2",
        kind=DailyQuestKind.PLAY_MATCHES,
        title="Завершить 2 PvP-матча",
        target=2,
        reward_tokens=35,
        reward_points=40,
    ),
    DailyQuestDefinition(
        quest_id="win_1",
        kind=DailyQuestKind.WIN_MATCHES,
        title="Победить в 1 PvP-матче",
        target=1,
        reward_tokens=30,
        reward_points=35,
    ),
    DailyQuestDefinition(
        quest_id="rated_2",
        kind=DailyQuestKind.RATED_MATCHES,
        title="Завершить 2 рейтинговых матча",
        target=2,
        reward_tokens=40,
        reward_points=45,
    ),
    DailyQuestDefinition(
        quest_id="opponents_2",
        kind=DailyQuestKind.UNIQUE_OPPONENTS,
        title="Сыграть с 2 разными соперниками",
        target=2,
        reward_tokens=45,
        reward_points=50,
    ),
    DailyQuestDefinition(
        quest_id="rated_win_1",
        kind=DailyQuestKind.RATED_WINS,
        title="Победить в рейтинговом матче",
        target=1,
        reward_tokens=35,
        reward_points=45,
    ),
)


@dataclass(frozen=True, slots=True)
class DailyQuestProgress:
    definition: DailyQuestDefinition
    progress: int
    claimed: bool

    @property
    def completed(self) -> bool:
        return self.progress >= self.definition.target

    @property
    def remaining(self) -> int:
        return max(0, self.definition.target - self.progress)


@dataclass(frozen=True, slots=True)
class ProgressionWalletView:
    user_id: int
    season: str
    tokens: int
    season_points: int
    daily_claims: int
    current_daily_streak: int
    best_daily_streak: int
    last_claim_date: date | None


@dataclass(frozen=True, slots=True)
class DailyProgressView:
    day: date
    window_start: datetime
    window_end: datetime
    quests: tuple[DailyQuestProgress, ...]
    wallet: ProgressionWalletView


@dataclass(frozen=True, slots=True)
class DailyClaimResult:
    claimed_quest_ids: tuple[str, ...]
    gained_tokens: int
    gained_points: int
    wallet: ProgressionWalletView


@dataclass(frozen=True, slots=True)
class SeasonTier:
    number: int
    name: str
    minimum_points: int
    next_minimum_points: int | None

    def progress_text(self, points: int) -> str:
        if self.next_minimum_points is None:
            return "максимальный уровень"
        gained = max(0, points - self.minimum_points)
        required = self.next_minimum_points - self.minimum_points
        return f"{gained}/{required}"


SEASON_TIERS: tuple[tuple[str, int], ...] = (
    ("Новичок", 0),
    ("Спорщик", 100),
    ("Оратор", 250),
    ("Тактик", 450),
    ("Мастер аргумента", 700),
    ("Легенда сезона", 1_000),
)


@dataclass(frozen=True, slots=True)
class SeasonStanding:
    user_id: int
    display_name: str
    username: str | None
    season: str
    season_points: int
    tokens: int
    current_daily_streak: int


@dataclass(frozen=True, slots=True)
class PvPAnalytics:
    user_id: int
    season: str
    rating: int | None
    rank: int | None
    total_matches: int
    rated_matches: int
    unrated_matches: int
    wins: int
    draws: int
    losses: int
    win_rate: float
    unique_opponents: int
    rating_delta_window: int
    current_win_streak: int
    best_win_streak: int
    pro_matches: int
    pro_wins: int
    con_matches: int
    con_wins: int
    window_days: int


@dataclass(frozen=True, slots=True)
class DailyMetrics:
    matches: int
    wins: int
    rated_matches: int
    unique_opponents: int
    rated_wins: int


def progression_day(now: datetime, reset_hour_utc: int) -> date:
    if not 0 <= reset_hour_utc <= 23:
        raise ValueError("reset_hour_utc must be between 0 and 23")
    normalized = now.astimezone(UTC)
    shifted = normalized - timedelta(hours=reset_hour_utc)
    return shifted.date()


def progression_window(day: date, reset_hour_utc: int) -> tuple[datetime, datetime]:
    if not 0 <= reset_hour_utc <= 23:
        raise ValueError("reset_hour_utc must be between 0 and 23")
    start = datetime(
        day.year,
        day.month,
        day.day,
        hour=reset_hour_utc,
        tzinfo=UTC,
    )
    return start, start + timedelta(days=1)


def daily_quests(day: date, *, count: int = 3) -> tuple[DailyQuestDefinition, ...]:
    if count <= 0:
        return ()
    ranked = sorted(
        DAILY_QUEST_CATALOG,
        key=lambda item: sha256(f"{day.isoformat()}:{item.quest_id}".encode()).digest(),
    )
    return tuple(ranked[: min(count, len(ranked))])


def quest_progress(definition: DailyQuestDefinition, metrics: DailyMetrics) -> int:
    values = {
        DailyQuestKind.PLAY_MATCHES: metrics.matches,
        DailyQuestKind.WIN_MATCHES: metrics.wins,
        DailyQuestKind.RATED_MATCHES: metrics.rated_matches,
        DailyQuestKind.UNIQUE_OPPONENTS: metrics.unique_opponents,
        DailyQuestKind.RATED_WINS: metrics.rated_wins,
    }
    return min(definition.target, values[definition.kind])


def season_tier(points: int) -> SeasonTier:
    normalized = max(0, points)
    index = 0
    for position, (_, minimum) in enumerate(SEASON_TIERS):
        if normalized >= minimum:
            index = position
        else:
            break
    name, minimum = SEASON_TIERS[index]
    next_minimum = SEASON_TIERS[index + 1][1] if index + 1 < len(SEASON_TIERS) else None
    return SeasonTier(
        number=index + 1,
        name=name,
        minimum_points=minimum,
        next_minimum_points=next_minimum,
    )
