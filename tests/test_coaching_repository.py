import importlib.util
from datetime import UTC, datetime, timedelta

import pytest

from bot.coaching_models import CoachingResult
from bot.coaching_repository import CoachingRepository
from bot.database import Database, PvPMatchRow, UserProfileRow

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("aiosqlite") is None,
    reason="aiosqlite is not installed in the local sandbox",
)


async def add_profiles(database: Database) -> None:
    async with database.sessions.begin() as db:
        for user_id in (1, 2, 3):
            db.add(
                UserProfileRow(
                    user_id=user_id,
                    username=f"user{user_id}",
                    display_name=f"User {user_id}",
                )
            )


def match_row(
    match_id: str,
    *,
    ended_at: datetime,
    pro_user_id: int = 1,
    con_user_id: int = 2,
    winner_user_id: int | None = 1,
    outcome: str = "judged",
    pro_scores: dict[str, int] | None = None,
    con_scores: dict[str, int] | None = None,
    pro_before: int = 1000,
    pro_after: int = 1012,
    con_before: int = 1000,
    con_after: int = 988,
    rated: bool = True,
) -> PvPMatchRow:
    return PvPMatchRow(
        match_id=match_id,
        season="season-1",
        topic=f"Topic {match_id}",
        pair_key=f"{min(pro_user_id, con_user_id)}:{max(pro_user_id, con_user_id)}",
        pro_user_id=pro_user_id,
        con_user_id=con_user_id,
        winner_user_id=winner_user_id,
        outcome=outcome,
        rated=rated,
        unrated_reason=None if rated else "pair limit",
        pro_rating_before=pro_before,
        pro_rating_after=pro_after,
        con_rating_before=con_before,
        con_rating_after=con_after,
        pro_scores=pro_scores or {},
        con_scores=con_scores or {},
        reason=f"Reason {match_id}",
        transcript=[],
        started_at=ended_at - timedelta(minutes=10),
        ended_at=ended_at,
    )


@pytest.mark.asyncio
async def test_match_review_uses_latest_scored_match_and_is_private() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_all_for_tests()
    await add_profiles(database)
    repository = CoachingRepository(database.sessions)
    now = datetime.now(UTC)

    async with database.sessions.begin() as db:
        db.add(
            match_row(
                "judged-1",
                ended_at=now,
                pro_scores={"logic": 8, "evidence": 7, "rebuttal": 9},
                con_scores={"logic": 6, "evidence": 7, "rebuttal": 6},
            )
        )
        db.add(
            match_row(
                "timeout-1",
                ended_at=now + timedelta(minutes=1),
                winner_user_id=2,
                outcome="timeout",
                pro_scores={},
                con_scores={},
                pro_after=988,
                con_after=1012,
            )
        )
        db.add(
            match_row(
                "foreign-1",
                ended_at=now + timedelta(minutes=2),
                pro_user_id=2,
                con_user_id=3,
                pro_scores={"logic": 7, "evidence": 7, "rebuttal": 7},
                con_scores={"logic": 6, "evidence": 6, "rebuttal": 6},
            )
        )

    latest = await repository.match_review(1, "season-1")
    foreign = await repository.match_review(1, "season-1", "foreign-1")
    timeout = await repository.match_review(1, "season-1", "timeout-1")

    assert latest is not None
    assert latest.match_id == "judged-1"
    assert latest.opponent_name == "User 2"
    assert latest.result is CoachingResult.WIN
    assert latest.rating_delta == 12
    assert latest.own_scores.total == 24
    assert latest.total_gap == 5
    assert foreign is None
    assert timeout is None
    await database.close()


@pytest.mark.asyncio
async def test_summary_calculates_averages_trend_results_and_stances() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_all_for_tests()
    await add_profiles(database)
    repository = CoachingRepository(database.sessions, window_matches=4)
    now = datetime.now(UTC)

    rows = [
        match_row(
            "m1",
            ended_at=now,
            winner_user_id=2,
            pro_scores={"logic": 3, "evidence": 4, "rebuttal": 5},
            con_scores={"logic": 7, "evidence": 7, "rebuttal": 7},
            pro_after=988,
            con_after=1012,
        ),
        match_row(
            "m2",
            ended_at=now + timedelta(minutes=1),
            pro_user_id=2,
            con_user_id=1,
            winner_user_id=None,
            outcome="draw",
            pro_scores={"logic": 5, "evidence": 5, "rebuttal": 5},
            con_scores={"logic": 4, "evidence": 5, "rebuttal": 6},
            pro_after=1000,
            con_after=1000,
        ),
        match_row(
            "m3",
            ended_at=now + timedelta(minutes=2),
            pro_scores={"logic": 7, "evidence": 7, "rebuttal": 7},
            con_scores={"logic": 6, "evidence": 6, "rebuttal": 6},
        ),
        match_row(
            "m4",
            ended_at=now + timedelta(minutes=3),
            pro_user_id=2,
            con_user_id=1,
            winner_user_id=1,
            pro_scores={"logic": 7, "evidence": 7, "rebuttal": 7},
            con_scores={"logic": 8, "evidence": 8, "rebuttal": 8},
            pro_after=988,
            con_after=1012,
        ),
        match_row(
            "timeout-latest",
            ended_at=now + timedelta(minutes=4),
            winner_user_id=2,
            outcome="timeout",
            pro_scores={},
            con_scores={},
            pro_after=988,
            con_after=1012,
        ),
    ]
    async with database.sessions.begin() as db:
        db.add_all(rows)

    summary = await repository.summary(1, "season-1")

    assert summary is not None
    assert summary.analyzed_matches == 4
    assert (summary.wins, summary.draws, summary.losses) == (2, 1, 1)
    assert summary.averages.logic == pytest.approx(5.5)
    assert summary.averages.evidence == pytest.approx(6.0)
    assert summary.averages.rebuttal == pytest.approx(6.5)
    assert summary.averages.total == pytest.approx(18.0)
    assert summary.trend_delta == pytest.approx(9.0)
    assert summary.pro_average_total == pytest.approx(16.5)
    assert summary.con_average_total == pytest.approx(19.5)
    await database.close()


def test_repository_validates_window() -> None:
    with pytest.raises(ValueError):
        CoachingRepository(None, window_matches=0)  # type: ignore[arg-type]

    with pytest.raises(ValueError):
        CoachingRepository(None, window_matches=51)  # type: ignore[arg-type]
