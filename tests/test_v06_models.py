from datetime import UTC, datetime, timedelta

import pytest

from bot.models import Stance
from bot.pvp_models import PvPMatch, PvPParticipant, PvPStatus


def make_match() -> PvPMatch:
    return PvPMatch(
        topic="Тест",
        season="s1",
        pro=PvPParticipant(user_id=1, display_name="A", stance=Stance.PRO),
        con=PvPParticipant(user_id=2, display_name="B", stance=Stance.CON),
    )


def test_deadline_is_renewed_after_turn() -> None:
    match = make_match()
    before = datetime.now(UTC)
    match.renew_deadline(60, now=before)
    assert match.seconds_until_deadline(now=before) == 60
    match.add_argument(1, "Аргумент", turn_timeout_seconds=90)
    assert match.current_user_id == 2
    assert match.turn_deadline is not None


def test_timeout_awards_win_to_opponent() -> None:
    match = make_match()
    match.add_argument(1, "Аргумент")
    match.turn_deadline = datetime.now(UTC) - timedelta(seconds=1)
    assert match.is_expired()
    winner = match.timeout(2)
    assert winner == 1
    assert match.winner_user_id == 1
    assert match.outcome == "timeout"
    assert match.status is PvPStatus.COMPLETED
    assert match.turn_deadline is None


def test_timeout_rejects_non_current_user() -> None:
    match = make_match()
    with pytest.raises(ValueError):
        match.timeout(2)
