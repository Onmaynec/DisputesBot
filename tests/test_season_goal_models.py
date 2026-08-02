from datetime import UTC, datetime

import pytest

from bot.season_goal_models import (
    GoalInputError,
    GoalMetric,
    MetricSnapshot,
    SeasonGoalView,
    format_metric_value,
    parse_metric,
    parse_target,
)


def test_metric_and_target_aliases() -> None:
    assert parse_metric("рейтинг") is GoalMetric.ELO
    assert parse_metric("win-rate") is GoalMetric.WIN_RATE
    assert parse_metric("логика") is GoalMetric.LOGIC
    assert parse_target(GoalMetric.LEAGUE, "Алмаз") == 1200
    assert parse_target(GoalMetric.WIN_RATE, "62,5") == pytest.approx(62.5)
    assert format_metric_value(GoalMetric.LEAGUE, 1450) == "👑 Грандмастер"


def test_target_validation() -> None:
    with pytest.raises(GoalInputError):
        parse_metric("unknown")
    with pytest.raises(GoalInputError):
        parse_target(GoalMetric.LEAGUE, "cosmic")
    with pytest.raises(GoalInputError):
        parse_target(GoalMetric.LOGIC, "11")
    with pytest.raises(GoalInputError):
        parse_target(GoalMetric.WINS, "2.5")


def test_goal_progress_is_bounded_and_completion_is_sticky() -> None:
    created = datetime.now(UTC)
    active = SeasonGoalView(
        metric=GoalMetric.ELO,
        baseline_value=1000,
        target_value=1200,
        current_value=1100,
        samples=5,
        completed_at=None,
        created_at=created,
    )
    regressed = SeasonGoalView(
        metric=GoalMetric.ELO,
        baseline_value=1000,
        target_value=1200,
        current_value=900,
        samples=5,
        completed_at=None,
        created_at=created,
    )
    completed = SeasonGoalView(
        metric=GoalMetric.ELO,
        baseline_value=1000,
        target_value=1200,
        current_value=1050,
        samples=5,
        completed_at=created,
        created_at=created,
    )

    assert active.progress == pytest.approx(0.5)
    assert active.progress_percent == 50
    assert regressed.progress == 0
    assert completed.progress == 1
    assert completed.progress_percent == 100


def test_snapshot_is_immutable_value_object() -> None:
    snapshot = MetricSnapshot(GoalMetric.WINS, 4.0, 7)
    assert snapshot.metric is GoalMetric.WINS
    assert snapshot.value == 4
    assert snapshot.samples == 7
