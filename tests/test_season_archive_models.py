from datetime import UTC, datetime

import pytest

from bot.league_models import league_status
from bot.season_archive_models import CareerSeason, CareerSummary


def season(
    name: str,
    *,
    rating: int,
    peak: int,
    games: int,
    wins: int,
) -> CareerSeason:
    return CareerSeason(
        season=name,
        rating=rating,
        starting_rating=1000,
        peak_rating=peak,
        rank=1,
        games=games,
        wins=wins,
        draws=1,
        losses=max(0, games - wins - 1),
        status=league_status(rating, games),
        last_activity=datetime.now(UTC),
    )


def test_career_metrics_and_best_season_are_deterministic() -> None:
    older = season("season-1", rating=1120, peak=1160, games=10, wins=6)
    newer = season("season-2", rating=1120, peak=1180, games=8, wins=5)
    career = CareerSummary(
        user_id=1,
        display_name="Player",
        username="player",
        seasons=(newer, older),
        total_games=18,
        total_wins=11,
        total_draws=2,
        total_losses=5,
        peak_rating=1180,
    )

    assert newer.net_rating == 120
    assert newer.win_rate == pytest.approx(62.5)
    assert career.win_rate == pytest.approx(11 * 100 / 18)
    assert career.best_season is newer


def test_empty_career_has_no_best_season() -> None:
    career = CareerSummary(
        user_id=1,
        display_name="Player",
        username=None,
        seasons=(),
        total_games=0,
        total_wins=0,
        total_draws=0,
        total_losses=0,
        peak_rating=0,
    )

    with pytest.raises(ValueError):
        _ = career.best_season
