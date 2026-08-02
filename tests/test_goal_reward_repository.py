import importlib.util

import pytest

from bot.database import Database, PvPPlayerRow, PvPProgressionRow, UserProfileRow
from bot.goal_reward_database import PvPGoalRewardClaimRow
from bot.goal_reward_models import GOAL_REWARD_CATALOG
from bot.goal_reward_repository import GoalRewardRepository
from bot.pvp_models import PvPUser
from bot.season_goal_models import GoalMetric
from bot.season_goal_repository import SeasonGoalRepository

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("aiosqlite") is None,
    reason="aiosqlite is not installed in the local sandbox",
)


USER = PvPUser(user_id=1, username="user1", display_name="User 1")


async def create_database() -> Database:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_all_for_tests()
    async with database.sessions.begin() as db:
        db.add(
            UserProfileRow(user_id=1, username="user1", display_name="User 1")
        )
        db.add(
            PvPPlayerRow(
                user_id=1,
                season="season-1",
                rating=1000,
                games=5,
                wins=0,
                draws=0,
                losses=5,
            )
        )
    return database


@pytest.mark.asyncio
async def test_claims_meaningful_goal_once_and_updates_wallet() -> None:
    database = await create_database()
    goals = SeasonGoalRepository(database.sessions)
    rewards = GoalRewardRepository(database.sessions, season_goal_repository=goals)

    await goals.set_goal(USER, "season-1", "elo", "1100")
    async with database.sessions.begin() as db:
        player = await db.get(PvPPlayerRow, {"user_id": 1, "season": "season-1"})
        assert player is not None
        player.rating = 1100

    first = await rewards.claim(USER, "season-1")
    assert first.claimed_metrics == (GoalMetric.ELO,)
    assert first.gained_tokens == 25
    assert first.gained_points == 40
    assert first.wallet_tokens == 25
    assert first.wallet_points == 40

    second = await rewards.claim(USER, "season-1")
    assert second.claimed_metrics == ()
    assert second.gained_tokens == 0
    assert second.gained_points == 0
    assert second.wallet_tokens == 25
    assert second.wallet_points == 40

    dashboard = await rewards.dashboard(1, "season-1")
    assert dashboard.claimable_count == 0
    assert dashboard.claimed_count == 1
    assert dashboard.rewards[0].is_claimed is True

    async with database.sessions() as db:
        claim = await db.get(
            PvPGoalRewardClaimRow,
            {"user_id": 1, "season": "season-1", "metric": "elo"},
        )
        wallet = await db.get(
            PvPProgressionRow,
            {"user_id": 1, "season": "season-1"},
        )
    assert claim is not None
    assert claim.baseline_value == 1000
    assert claim.target_value == 1100
    assert wallet is not None
    assert wallet.tokens == 25
    assert wallet.season_points == 40
    await database.close()


@pytest.mark.asyncio
async def test_completed_trivial_goal_is_not_rewardable() -> None:
    database = await create_database()
    goals = SeasonGoalRepository(database.sessions)
    rewards = GoalRewardRepository(database.sessions, season_goal_repository=goals)

    await goals.set_goal(USER, "season-1", "elo", "1020")
    async with database.sessions.begin() as db:
        player = await db.get(PvPPlayerRow, {"user_id": 1, "season": "season-1"})
        assert player is not None
        player.rating = 1020

    result = await rewards.claim(USER, "season-1")
    assert result.claimed_metrics == ()
    assert result.wallet_tokens == 0
    assert result.wallet_points == 0

    dashboard = await rewards.dashboard(1, "season-1")
    assert len(dashboard.rewards) == 1
    view = dashboard.rewards[0]
    assert view.is_completed is True
    assert view.qualifies is False
    assert view.is_claimable is False
    await database.close()


@pytest.mark.asyncio
async def test_multiple_metrics_reactivation_and_season_isolation() -> None:
    database = await create_database()
    goals = SeasonGoalRepository(database.sessions)
    rewards = GoalRewardRepository(database.sessions, season_goal_repository=goals)

    await goals.set_goal(USER, "season-1", "wins", "3")
    await goals.set_goal(USER, "season-1", "matches", "10")
    async with database.sessions.begin() as db:
        player = await db.get(PvPPlayerRow, {"user_id": 1, "season": "season-1"})
        assert player is not None
        player.games = 10
        player.wins = 3
        player.losses = 7

    first = await rewards.claim(USER, "season-1")
    assert set(first.claimed_metrics) == {GoalMetric.WINS, GoalMetric.MATCHES}
    assert first.gained_tokens == 35
    assert first.gained_points == 55

    await goals.set_goal(USER, "season-1", "wins", "6")
    async with database.sessions.begin() as db:
        player = await db.get(PvPPlayerRow, {"user_id": 1, "season": "season-1"})
        assert player is not None
        player.wins = 6
    repeated_metric = await rewards.claim(USER, "season-1")
    assert repeated_metric.claimed_metrics == ()
    assert repeated_metric.wallet_tokens == 35

    async with database.sessions.begin() as db:
        db.add(
            PvPPlayerRow(
                user_id=1,
                season="season-2",
                rating=1000,
                games=5,
                wins=0,
                draws=0,
                losses=5,
            )
        )
    await goals.set_goal(USER, "season-2", "wins", "3")
    async with database.sessions.begin() as db:
        player = await db.get(PvPPlayerRow, {"user_id": 1, "season": "season-2"})
        assert player is not None
        player.wins = 3
    next_season = await rewards.claim(USER, "season-2")
    assert next_season.claimed_metrics == (GoalMetric.WINS,)
    assert next_season.gained_tokens == 20
    assert next_season.wallet_tokens == 20
    await database.close()


@pytest.mark.asyncio
async def test_delete_user_data_removes_claim_audit_rows() -> None:
    database = await create_database()
    goals = SeasonGoalRepository(database.sessions)
    rewards = GoalRewardRepository(database.sessions, season_goal_repository=goals)

    await goals.set_goal(USER, "season-1", "elo", "1100")
    async with database.sessions.begin() as db:
        player = await db.get(PvPPlayerRow, {"user_id": 1, "season": "season-1"})
        assert player is not None
        player.rating = 1100
    await rewards.claim(USER, "season-1")

    await rewards.delete_user_data(1)
    async with database.sessions() as db:
        rows = list(
            await db.scalars(
                __import__("sqlalchemy").select(PvPGoalRewardClaimRow).where(
                    PvPGoalRewardClaimRow.user_id == 1
                )
            )
        )
    assert rows == []
    await database.close()


def test_reward_catalog_covers_every_goal_metric_once() -> None:
    metrics = [item.metric for item in GOAL_REWARD_CATALOG]
    assert len(metrics) == len(GoalMetric)
    assert len(set(metrics)) == len(metrics)
    assert all(item.reward_tokens > 0 for item in GOAL_REWARD_CATALOG)
    assert all(item.reward_points > 0 for item in GOAL_REWARD_CATALOG)
