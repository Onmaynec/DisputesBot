from datetime import UTC, datetime

import pytest

from bot.league_models import league_status
from bot.season_insight_models import (
    CareerRecords,
    SeasonComparison,
    SeasonRecap,
    SeasonSkillAverages,
)


def recap(
    season: str,
    *,
    rating: int,
    starting: int,
    peak: int,
    games: int,
    wins: int,
    streak: int,
    skills: SeasonSkillAverages | None = None,
) -> SeasonRecap:
    return SeasonRecap(
        user_id=1,
        season=season,
        rating=rating,
        starting_rating=starting,
        peak_rating=peak,
        rank=1,
        total_players=4,
        games=games,
        wins=wins,
        draws=1,
        losses=max(0, games - wins - 1),
        rated_matches=games,
        unrated_matches=0,
        unique_opponents=3,
        longest_win_streak=streak,
        favorite_opponent_id=2,
        favorite_opponent_name="User 2",
        favorite_opponent_matches=3,
        claimed_milestones=2,
        claimed_tokens=40,
        skills=skills,
        status=league_status(rating, games),
        last_activity=datetime.now(UTC),
    )


def test_skill_averages_use_deterministic_ties() -> None:
    scores = SeasonSkillAverages(
        logic=7.0,
        evidence=7.0,
        rebuttal=6.0,
        scored_matches=4,
    )

    assert scores.total == pytest.approx(20.0)
    assert scores.strongest_key == "logic"
    assert scores.strongest_label == "логика"
    assert scores.focus_key == "rebuttal"
    assert scores.focus_label == "опровержение"


def test_comparison_calculates_season_deltas() -> None:
    older = recap(
        "season-1",
        rating=1020,
        starting=1000,
        peak=1040,
        games=10,
        wins=5,
        streak=2,
        skills=SeasonSkillAverages(6.0, 6.0, 6.0, 5),
    )
    newer = recap(
        "season-2",
        rating=1100,
        starting=1000,
        peak=1120,
        games=12,
        wins=8,
        streak=4,
        skills=SeasonSkillAverages(7.0, 7.0, 7.0, 6),
    )
    comparison = SeasonComparison(older=older, newer=newer)

    assert comparison.rating_delta == 80
    assert comparison.peak_delta == 80
    assert comparison.games_delta == 2
    assert comparison.streak_delta == 2
    assert comparison.win_rate_delta == pytest.approx(16.6666666)
    assert comparison.skill_total_delta == pytest.approx(3.0)


def test_career_records_reports_season_count() -> None:
    first = recap(
        "season-1",
        rating=1020,
        starting=1000,
        peak=1040,
        games=10,
        wins=5,
        streak=2,
    )
    second = recap(
        "season-2",
        rating=1100,
        starting=1000,
        peak=1120,
        games=12,
        wins=8,
        streak=4,
    )
    records = CareerRecords(
        user_id=1,
        seasons=(second, first),
        highest_final=second,
        highest_peak=second,
        most_wins=second,
        most_games=second,
        best_win_rate=second,
        biggest_gain=second,
        longest_streak=second,
    )

    assert records.seasons_count == 2
    assert second.net_rating == 100
    assert second.win_rate == pytest.approx(8 * 100 / 12)
