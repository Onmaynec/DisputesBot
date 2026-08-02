from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .database import PvPProgressionRow, UserProfileRow
from .goal_reward_database import PvPGoalRewardClaimRow
from .goal_reward_models import (
    GoalRewardClaimResult,
    GoalRewardDashboard,
    GoalRewardView,
    reward_for,
)
from .pvp_models import PvPUser
from .season_goal_database import PvPSeasonGoalRow
from .season_goal_models import GoalMetric
from .season_goal_repository import SeasonGoalRepository


class GoalRewardRepository:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        *,
        season_goal_repository: SeasonGoalRepository | None = None,
    ) -> None:
        self.sessions = sessions
        self.season_goal_repository = season_goal_repository or SeasonGoalRepository(sessions)

    async def dashboard(self, user_id: int, season: str) -> GoalRewardDashboard:
        refreshed = await self.season_goal_repository.dashboard(user_id, season)
        async with self.sessions() as db:
            goal_rows = list(
                await db.scalars(
                    select(PvPSeasonGoalRow)
                    .where(
                        PvPSeasonGoalRow.user_id == user_id,
                        PvPSeasonGoalRow.season == refreshed.season,
                    )
                    .order_by(PvPSeasonGoalRow.created_at.asc(), PvPSeasonGoalRow.metric.asc())
                )
            )
            claim_rows = list(
                await db.scalars(
                    select(PvPGoalRewardClaimRow)
                    .where(
                        PvPGoalRewardClaimRow.user_id == user_id,
                        PvPGoalRewardClaimRow.season == refreshed.season,
                    )
                    .order_by(
                        PvPGoalRewardClaimRow.claimed_at.asc(),
                        PvPGoalRewardClaimRow.metric.asc(),
                    )
                )
            )
            wallet = await db.get(
                PvPProgressionRow,
                {"user_id": user_id, "season": refreshed.season},
            )

        claims = {row.metric: row for row in claim_rows}
        views: list[GoalRewardView] = []
        seen: set[str] = set()
        for goal in goal_rows:
            claim = claims.get(goal.metric)
            view = self._view_from_claim(claim) if claim is not None else self._view_from_goal(goal)
            if view is not None:
                views.append(view)
                seen.add(goal.metric)
        for claim in claim_rows:
            if claim.metric in seen:
                continue
            view = self._view_from_claim(claim)
            if view is not None:
                views.append(view)

        return GoalRewardDashboard(
            user_id=user_id,
            season=refreshed.season,
            rewards=tuple(views),
            wallet_tokens=wallet.tokens if wallet is not None else 0,
            wallet_points=wallet.season_points if wallet is not None else 0,
        )

    async def claim(
        self,
        user: PvPUser,
        season: str,
        *,
        now: datetime | None = None,
    ) -> GoalRewardClaimResult:
        refreshed = await self.season_goal_repository.dashboard(user.user_id, season, now=now)
        reference = now or datetime.now(UTC)

        async with self.sessions.begin() as db:
            profile = await db.get(UserProfileRow, user.user_id, with_for_update=True)
            if profile is None:
                profile = UserProfileRow(
                    user_id=user.user_id,
                    username=user.username,
                    display_name=user.display_name,
                )
                db.add(profile)
                await db.flush()
            else:
                profile.username = user.username
                profile.display_name = user.display_name
                profile.updated_at = reference

            goals = list(
                await db.scalars(
                    select(PvPSeasonGoalRow)
                    .where(
                        PvPSeasonGoalRow.user_id == user.user_id,
                        PvPSeasonGoalRow.season == refreshed.season,
                    )
                    .with_for_update()
                )
            )
            claims = list(
                await db.scalars(
                    select(PvPGoalRewardClaimRow)
                    .where(
                        PvPGoalRewardClaimRow.user_id == user.user_id,
                        PvPGoalRewardClaimRow.season == refreshed.season,
                    )
                    .with_for_update()
                )
            )
            claimed_metrics = {row.metric for row in claims}

            wallet = await db.get(
                PvPProgressionRow,
                {"user_id": user.user_id, "season": refreshed.season},
                with_for_update=True,
            )
            if wallet is None:
                wallet = PvPProgressionRow(user_id=user.user_id, season=refreshed.season)
                db.add(wallet)
                await db.flush()

            completed: list[tuple[PvPSeasonGoalRow, GoalMetric]] = []
            for goal in goals:
                if goal.completed_at is None or goal.metric in claimed_metrics:
                    continue
                try:
                    metric = GoalMetric(goal.metric)
                except ValueError:
                    continue
                view = self._view_from_goal(goal)
                if view is not None and view.qualifies:
                    completed.append((goal, metric))

            gained_tokens = 0
            gained_points = 0
            for goal, metric in completed:
                reward = reward_for(metric)
                gained_tokens += reward.reward_tokens
                gained_points += reward.reward_points
                db.add(
                    PvPGoalRewardClaimRow(
                        user_id=user.user_id,
                        season=refreshed.season,
                        metric=metric.value,
                        baseline_value=goal.baseline_value,
                        target_value=goal.target_value,
                        reward_tokens=reward.reward_tokens,
                        reward_points=reward.reward_points,
                        completed_at=goal.completed_at,
                        claimed_at=reference,
                    )
                )

            if completed:
                wallet.tokens += gained_tokens
                wallet.season_points += gained_points
                wallet.updated_at = reference
                await db.flush()

            result = GoalRewardClaimResult(
                claimed_metrics=tuple(metric for _, metric in completed),
                gained_tokens=gained_tokens,
                gained_points=gained_points,
                wallet_tokens=wallet.tokens,
                wallet_points=wallet.season_points,
            )
        return result

    async def delete_user_data(self, user_id: int) -> None:
        async with self.sessions.begin() as db:
            await db.execute(
                delete(PvPGoalRewardClaimRow).where(
                    PvPGoalRewardClaimRow.user_id == user_id
                )
            )

    @staticmethod
    def _view_from_goal(row: PvPSeasonGoalRow) -> GoalRewardView | None:
        try:
            metric = GoalMetric(row.metric)
        except ValueError:
            return None
        reward = reward_for(metric)
        return GoalRewardView(
            metric=metric,
            baseline_value=row.baseline_value,
            target_value=row.target_value,
            completed_at=row.completed_at,
            claimed_at=None,
            reward_tokens=reward.reward_tokens,
            reward_points=reward.reward_points,
            minimum_delta=reward.minimum_delta,
        )

    @staticmethod
    def _view_from_claim(row: PvPGoalRewardClaimRow) -> GoalRewardView | None:
        try:
            metric = GoalMetric(row.metric)
        except ValueError:
            return None
        reward = reward_for(metric)
        return GoalRewardView(
            metric=metric,
            baseline_value=row.baseline_value,
            target_value=row.target_value,
            completed_at=row.completed_at,
            claimed_at=row.claimed_at,
            reward_tokens=row.reward_tokens,
            reward_points=row.reward_points,
            minimum_delta=reward.minimum_delta,
        )
