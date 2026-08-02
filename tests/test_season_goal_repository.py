import importlib.util
from datetime import UTC, datetime, timedelta

import pytest

from bot.database import Database, PvPMatchRow, PvPPlayerRow, UserProfileRow
from bot.pvp_models import PvPUser
from bot.season_goal_models import GoalInputError, GoalLimitError, GoalMetric
from bot.season_goal_repository import SeasonGoalRepository

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("aiosqlite") is None,
    reason="aiosqlite is not installed in the local sandbox",
)


USER = PvPUser(user_id=1, username="user1", display_name="User 1")


def match_row(
    match_id: str,
    *,
    ended_at: datetime,
    winner_user_id: int | None = 1,
    pro_scores: dict[str, int] | None = None,
    con_scores: dict[str, int] | None = None,
    pro_before: int = 1000,
    pro_after: int = 1010,
) -> PvPMatchRow:
    return PvPMatchRow(
        match_id=match_id,
        season="season-1",
        topic=f"Topic {match_id}",
        pair_key="1:2",
        pro_user_id=1,
        con_user_id=2,
        winner_user_id=winner_user_id,
        outcome="judged" if winner_user_id is not None else "draw",
        rated=True,
        unrated_reason=None,
        pro_rating_before=pro_before,
        pro_rating_after=pro_after,
        con_rating_before=1000,
        con_rating_after=990,
        pro_scores=pro_scores or {},
        con_scores=con_scores or {},
        reason=f"Reason {match_id}",
        transcript=[],
        started_at=ended_at - timedelta(minutes=5),
        ended_at=ended_at,
    )


async def add_profiles_and_player(
    database: Database,
    *,
    rating: int = 1000,
    games: int = 5,
    wins: int = 0,
    draws: int = 0,
    losses: int = 0,
) -> None:
    async with database.sessions.begin() as db:
        db.add_all(
            [
                UserProfileRow(user_id=1, username="user1", display_name="User 1"),
                UserProfileRow(user_id=2, username="user2", display_name="User 2"),
                PvPPlayerRow(
                    user_id=1,
                    season="season-1",
                    rating=rating,
                    games=games,
                    wins=wins,
                    draws=draws,
                    losses=losses,
                ),
            ]
        )


@pytest.mark.asyncio
async def test_elo_goal_completion_remains_sticky_after_rating_drop() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_all_for_tests()
    await add_profiles_and_player(database, rating=1000)
    repository = SeasonGoalRepository(database.sessions)

    result = await repository.set_goal(USER, "season-1", "elo", "1100")
    assert result.created is True
    assert result.goal.baseline_value == 1000
    assert result.goal.progress == 0

    async with database.sessions.begin() as db:
        player = await db.get(PvPPlayerRow, {"user_id": 1, "season": "season-1"})
        assert player is not None
        player.rating = 1100

    completed = await repository.dashboard(1, "season-1")
    assert completed.goals[0].is_completed is True
    assert completed.goals[0].progress_percent == 100

    async with database.sessions.begin() as db:
        player = await db.get(PvPPlayerRow, {"user_id": 1, "season": "season-1"})
        assert player is not None
        player.rating = 1040

    after_drop = await repository.dashboard(1, "season-1")
    assert after_drop.goals[0].is_completed is True
    assert after_drop.goals[0].progress_percent == 100
    await database.close()


@pytest.mark.asyncio
async def test_sample_gates_for_win_rate_and_skill_goals() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_all_for_tests()
    await add_profiles_and_player(database, games=2, wins=2)
    repository = SeasonGoalRepository(database.sessions)
    now = datetime.now(UTC)

    async with database.sessions.begin() as db:
        db.add_all(
            [
                match_row(
                    "m1",
                    ended_at=now,
                    pro_scores={"logic": 8, "evidence": 7, "rebuttal": 6},
                    con_scores={"logic": 6, "evidence": 6, "rebuttal": 6},
                ),
                match_row(
                    "m2",
                    ended_at=now + timedelta(minutes=1),
                    pro_scores={"logic": 8, "evidence": 7, "rebuttal": 6},
                    con_scores={"logic": 6, "evidence": 6, "rebuttal": 6},
                ),
            ]
        )

    await repository.set_goal(USER, "season-1", "win_rate", "100")
    await repository.set_goal(USER, "season-1", "logic", "8")
    initial = await repository.dashboard(1, "season-1")
    by_metric = {goal.metric: goal for goal in initial.goals}
    assert by_metric[GoalMetric.WIN_RATE].is_completed is False
    assert by_metric[GoalMetric.WIN_RATE].sample_requirement_met is False
    assert by_metric[GoalMetric.LOGIC].is_completed is False
    assert by_metric[GoalMetric.LOGIC].sample_requirement_met is False

    async with database.sessions.begin() as db:
        db.add(
            match_row(
                "m3",
                ended_at=now + timedelta(minutes=2),
                pro_scores={"logic": 8, "evidence": 7, "rebuttal": 6},
                con_scores={"logic": 6, "evidence": 6, "rebuttal": 6},
            )
        )
        player = await db.get(PvPPlayerRow, {"user_id": 1, "season": "season-1"})
        assert player is not None
        player.games = 3
        player.wins = 3

    after_three = await repository.dashboard(1, "season-1")
    by_metric = {goal.metric: goal for goal in after_three.goals}
    assert by_metric[GoalMetric.LOGIC].is_completed is True
    assert by_metric[GoalMetric.WIN_RATE].is_completed is False

    async with database.sessions.begin() as db:
        db.add_all(
            [
                match_row("m4", ended_at=now + timedelta(minutes=3)),
                match_row("m5", ended_at=now + timedelta(minutes=4)),
            ]
        )
        player = await db.get(PvPPlayerRow, {"user_id": 1, "season": "season-1"})
        assert player is not None
        player.games = 5
        player.wins = 5

    final = await repository.dashboard(1, "season-1")
    by_metric = {goal.metric: goal for goal in final.goals}
    assert by_metric[GoalMetric.WIN_RATE].is_completed is True
    assert by_metric[GoalMetric.LOGIC].is_completed is True
    await database.close()


@pytest.mark.asyncio
async def test_limit_delete_suggestions_and_privacy_deletion() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_all_for_tests()
    await add_profiles_and_player(database, games=5, wins=0)
    repository = SeasonGoalRepository(database.sessions, max_active_goals=2)

    await repository.set_goal(USER, "season-1", "wins", "5")
    await repository.set_goal(USER, "season-1", "matches", "10")
    with pytest.raises(GoalLimitError):
        await repository.set_goal(USER, "season-1", "streak", "2")

    assert await repository.delete_goal(1, "season-1", "wins") is True
    assert await repository.delete_goal(1, "season-1", "wins") is False
    await repository.set_goal(USER, "season-1", "streak", "2")

    suggestions = await repository.suggestions(1, "season-1")
    metrics = {suggestion.metric for suggestion in suggestions}
    assert GoalMetric.MATCHES not in metrics
    assert GoalMetric.STREAK not in metrics
    assert len(suggestions) <= 3

    await repository.delete_user_data(1)
    dashboard = await repository.dashboard(1, "season-1")
    assert dashboard.goals == ()
    await database.close()


@pytest.mark.asyncio
async def test_rejects_already_achieved_and_invalid_goals() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_all_for_tests()
    await add_profiles_and_player(database, rating=1200, games=5, wins=3)
    repository = SeasonGoalRepository(database.sessions)

    with pytest.raises(GoalInputError):
        await repository.set_goal(USER, "season-1", "elo", "1200")
    with pytest.raises(GoalInputError):
        await repository.set_goal(USER, "season-1", "unknown", "10")
    with pytest.raises(GoalInputError):
        await repository.set_goal(USER, "", "wins", "10")

    league = await repository.set_goal(USER, "season-1", "league", "master")
    assert league.goal.metric is GoalMetric.LEAGUE
    assert league.goal.target_value == 1300
    await database.close()
