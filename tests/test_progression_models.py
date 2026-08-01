from datetime import UTC, date, datetime

from bot.progression_models import (
    DailyMetrics,
    daily_quests,
    progression_day,
    quest_progress,
    season_tier,
)


def test_daily_quests_are_deterministic_and_unique() -> None:
    day = date(2026, 8, 1)

    first = daily_quests(day)
    second = daily_quests(day)

    assert first == second
    assert len(first) == 3
    assert len({item.quest_id for item in first}) == 3


def test_progression_day_respects_reset_hour() -> None:
    before_reset = datetime(2026, 8, 1, 4, 59, tzinfo=UTC)
    after_reset = datetime(2026, 8, 1, 5, 0, tzinfo=UTC)

    assert progression_day(before_reset, 5) == date(2026, 7, 31)
    assert progression_day(after_reset, 5) == date(2026, 8, 1)


def test_all_catalog_metrics_are_capped_at_target() -> None:
    metrics = DailyMetrics(
        matches=20,
        wins=20,
        rated_matches=20,
        unique_opponents=20,
        rated_wins=20,
    )

    for quest in daily_quests(date(2026, 8, 2)):
        assert quest_progress(quest, metrics) == quest.target


def test_season_tier_reports_next_threshold() -> None:
    tier = season_tier(275)
    maximum = season_tier(5_000)

    assert tier.name == "Оратор"
    assert tier.progress_text(275) == "25/200"
    assert maximum.name == "Легенда сезона"
    assert maximum.progress_text(5_000) == "максимальный уровень"
