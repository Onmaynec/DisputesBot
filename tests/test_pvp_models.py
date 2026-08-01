import pytest

from bot.models import Stance
from bot.pvp_models import PvPMatch, PvPParticipant, PvPStatus


def make_match() -> PvPMatch:
    return PvPMatch(
        topic="Удалённая работа лучше офисной",
        season="season-1",
        pro=PvPParticipant(user_id=1, display_name="Pro", stance=Stance.PRO),
        con=PvPParticipant(user_id=2, display_name="Con", stance=Stance.CON),
    )


def test_pvp_turns_alternate_and_finish_after_six_arguments() -> None:
    match = make_match()

    for turn, user_id in enumerate([1, 2, 1, 2, 1, 2], start=1):
        match.add_argument(user_id, f"Аргумент номер {turn}")

    assert match.status is PvPStatus.JUDGING
    assert match.current_user_id is None
    assert match.argument_count(1) == 3
    assert match.argument_count(2) == 3


def test_pvp_rejects_argument_out_of_turn() -> None:
    match = make_match()

    with pytest.raises(ValueError, match="turn"):
        match.add_argument(2, "Попытка сходить первым")


def test_unstarted_match_can_cancel_without_rating() -> None:
    match = make_match()

    match.cancel()

    assert match.status is PvPStatus.CANCELLED
    assert match.outcome == "cancelled"


def test_forfeit_assigns_opponent_as_winner() -> None:
    match = make_match()
    match.add_argument(1, "Первый аргумент")

    winner = match.forfeit(1)

    assert winner == 2
    assert match.winner_user_id == 2
    assert match.outcome == "forfeit"
