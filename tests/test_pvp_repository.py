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
async def test_pvp_repository_updates_both_ratings_once() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_all_for_tests()
    repository = PvPRepository(database.sessions)
    match, judgement = completed_match()

    first = await repository.record_match(match, judgement=judgement)
    second = await repository.record_match(match, judgement=judgement)
    pro = await repository.rating(1, "season-1")
    con = await repository.rating(2, "season-1")

    assert first.created
    assert not second.created
    assert pro is not None and con is not None
    assert pro.rating == 1016
    assert con.rating == 984
    assert pro.games == con.games == 1
    assert first.pro_delta + first.con_delta == 0
    assert len(await repository.history(1)) == 1
    assert len(await repository.history(2)) == 1
    await database.close()


@pytest.mark.asyncio
async def test_profile_deletion_removes_related_pvp_history() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_all_for_tests()
    repository = PvPRepository(database.sessions)
    match, judgement = completed_match()
    await repository.record_match(match, judgement=judgement)
    await repository.delete_user_data(1)

    assert await repository.history(2) == []
    assert await repository.rating(1, "season-1") is None
    await database.close()
