import importlib.util

import pytest

from bot.database import Database
from bot.models import ScoreBreakdown, Stance
from bot.pvp_models import PvPJudgement, PvPMatch, PvPParticipant
from bot.pvp_repository import PvPRepository

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("aiosqlite") is None,
    reason="aiosqlite is not installed in the local sandbox",
)


def completed_match() -> tuple[PvPMatch, PvPJudgement]:
    match = PvPMatch(
        topic="Тема",
        season="season-1",
        pro=PvPParticipant(user_id=1, display_name="One", stance=Stance.PRO),
        con=PvPParticipant(user_id=2, display_name="Two", stance=Stance.CON),
    )
    for user_id in [1, 2, 1, 2, 1, 2]:
        match.add_argument(user_id, "Содержательный аргумент")
    judgement = PvPJudgement(
        winner_user_id=1,
        pro_scores=ScoreBreakdown(logic=8, evidence=7, rebuttal=8),
        con_scores=ScoreBreakdown(logic=7, evidence=7, rebuttal=6),
        reasoning="Сторона за точнее связала тезисы с последствиями и ответила на возражения.",
        decisive_point="Более сильная работа с контраргументом.",
    )
    match.complete_judging(1, judgement.reasoning)
    return match, judgement


@pytest.mark.asyncio
async def test_repeat_pair_becomes_unrated() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_all_for_tests()
    repository = PvPRepository(
        database.sessions,
        max_rated_pair_matches=1,
        repeat_window_seconds=86_400,
    )
    first_match, first_judgement = completed_match()
    second_match, second_judgement = completed_match()

    first = await repository.record_match(first_match, judgement=first_judgement)
    second = await repository.record_match(second_match, judgement=second_judgement)
    pro = await repository.rating(1, "season-1")

    assert first.entry.rated
    assert not second.entry.rated
    assert second.pro_delta == second.con_delta == 0
    assert pro is not None and pro.rating == 1016 and pro.games == 2
    await database.close()
