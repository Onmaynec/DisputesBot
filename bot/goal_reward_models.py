from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .season_goal_models import GoalMetric


@dataclass(frozen=True, slots=True)
class GoalRewardDefinition:
    metric: GoalMetric
    reward_tokens: int
    reward_points: int
    minimum_delta: float


GOAL_REWARD_CATALOG: tuple[GoalRewardDefinition, ...] = (
    GoalRewardDefinition(GoalMetric.ELO, 25, 40, 50.0),
    GoalRewardDefinition(GoalMetric.LEAGUE, 35, 60, 0.0),
    GoalRewardDefinition(GoalMetric.WINS, 20, 30, 3.0),
    GoalRewardDefinition(GoalMetric.MATCHES, 15, 25, 5.0),
    GoalRewardDefinition(GoalMetric.WIN_RATE, 25, 40, 5.0),
    GoalRewardDefinition(GoalMetric.STREAK, 25, 40, 2.0),
    GoalRewardDefinition(GoalMetric.LOGIC, 30, 45, 0.5),
    GoalRewardDefinition(GoalMetric.EVIDENCE, 30, 45, 0.5),
    GoalRewardDefinition(GoalMetric.REBUTTAL, 30, 45, 0.5),
)

_REWARD_BY_METRIC = {item.metric: item for item in GOAL_REWARD_CATALOG}


@dataclass(frozen=True, slots=True)
class GoalRewardView:
    metric: GoalMetric
    baseline_value: float
    target_value: float
    completed_at: datetime | None
    claimed_at: datetime | None
    reward_tokens: int
    reward_points: int
    minimum_delta: float

    @property
    def challenge_delta(self) -> float:
        return self.target_value - self.baseline_value

    @property
    def qualifies(self) -> bool:
        if self.metric is GoalMetric.LEAGUE:
            return self.target_value > self.baseline_value
        return self.challenge_delta + 1e-9 >= self.minimum_delta

    @property
    def is_completed(self) -> bool:
        return self.completed_at is not None

    @property
    def is_claimed(self) -> bool:
        return self.claimed_at is not None

    @property
    def is_claimable(self) -> bool:
        return self.is_completed and self.qualifies and not self.is_claimed


@dataclass(frozen=True, slots=True)
class GoalRewardDashboard:
    user_id: int
    season: str
    rewards: tuple[GoalRewardView, ...]
    wallet_tokens: int
    wallet_points: int

    @property
    def claimable_count(self) -> int:
        return sum(item.is_claimable for item in self.rewards)

    @property
    def claimed_count(self) -> int:
        return sum(item.is_claimed for item in self.rewards)


@dataclass(frozen=True, slots=True)
class GoalRewardClaimResult:
    claimed_metrics: tuple[GoalMetric, ...]
    gained_tokens: int
    gained_points: int
    wallet_tokens: int
    wallet_points: int


def reward_for(metric: GoalMetric) -> GoalRewardDefinition:
    return _REWARD_BY_METRIC[metric]
