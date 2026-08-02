import pytest

from bot.league_models import LeagueId, league_for_rating, league_status


def test_placement_hides_division_until_five_games() -> None:
    status = league_status(1_250, 4)

    assert status.is_placement is True
    assert status.placement_remaining == 1
    assert status.name == "Калибровка"


def test_division_thresholds_and_progress() -> None:
    silver = league_for_rating(999)
    gold = league_for_rating(1_000)
    master = league_for_rating(1_400)

    assert silver.league_id is LeagueId.SILVER
    assert silver.rating_to_next(999) == 1
    assert gold.league_id is LeagueId.GOLD
    assert gold.progress_text(1_050) == "50/100"
    assert master.league_id is LeagueId.MASTER
    assert master.rating_to_next(1_400) == 50


def test_grandmaster_is_open_ended() -> None:
    division = league_for_rating(2_000)

    assert division.league_id is LeagueId.GRANDMASTER
    assert division.progress_text(2_000) == "максимальный дивизион"
    assert division.rating_to_next(2_000) == 0


def test_invalid_placement_requirement_is_rejected() -> None:
    with pytest.raises(ValueError):
        league_status(1_000, 10, placement_games=-1)
