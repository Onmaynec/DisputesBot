from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from statistics import fmean

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .database import PvPMatchRow, PvPPlayerRow, UserProfileRow
from .league_models import DEFAULT_PLACEMENT_GAMES, LEAGUE_CATALOG
from .pvp_models import PvPUser
from .season_goal_database import PvPSeasonGoalRow
from .season_goal_models import (
    GOAL_DEFINITIONS,
    GoalDashboard,
    GoalInputError,
    GoalLimitError,
    GoalMetric,
    GoalSetResult,
    GoalSuggestion,
    MetricSnapshot,
    SeasonGoalView,
    definition_for,
    parse_metric,
    parse_target,
)


class SeasonGoalRepository:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        *,
        placement_games: int = DEFAULT_PLACEMENT_GAMES,
        max_active_goals: int = 5,
    ) -> None:
        if placement_games < 0:
            raise ValueError("placement_games must not be negative")
        if not 1 <= max_active_goals <= len(GOAL_DEFINITIONS):
            raise ValueError("max_active_goals is outside the supported range")
        self.sessions = sessions
        self.placement_games = placement_games
        self.max_active_goals = max_active_goals

    async def dashboard(
        self,
        user_id: int,
        season: str,
        *,
        now: datetime | None = None,
    ) -> GoalDashboard:
        normalized_season = self._normalize_season(season)
        reference = now or datetime.now(UTC)
        async with self.sessions.begin() as db:
            rows = list(
                await db.scalars(
                    select(PvPSeasonGoalRow)
                    .where(
                        PvPSeasonGoalRow.user_id == user_id,
                        PvPSeasonGoalRow.season == normalized_season,
                    )
                    .order_by(
                        PvPSeasonGoalRow.completed_at.is_not(None),
                        PvPSeasonGoalRow.created_at.asc(),
                        PvPSeasonGoalRow.metric.asc(),
                    )
                    .with_for_update()
                )
            )
            snapshots = await self._snapshots(db, user_id, normalized_season)
            views = self._refresh_rows(rows, snapshots, reference)
        return GoalDashboard(
            user_id=user_id,
            season=normalized_season,
            goals=tuple(views),
        )

    async def set_goal(
        self,
        user: PvPUser,
        season: str,
        metric_raw: str,
        target_raw: str,
        *,
        now: datetime | None = None,
    ) -> GoalSetResult:
        normalized_season = self._normalize_season(season)
        metric = parse_metric(metric_raw)
        target = parse_target(metric, target_raw)
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

            rows = list(
                await db.scalars(
                    select(PvPSeasonGoalRow)
                    .where(
                        PvPSeasonGoalRow.user_id == user.user_id,
                        PvPSeasonGoalRow.season == normalized_season,
                    )
                    .with_for_update()
                )
            )
            snapshots = await self._snapshots(db, user.user_id, normalized_season)
            snapshot = snapshots[metric]
            definition = definition_for(metric)
            if (
                snapshot.value >= target
                and snapshot.samples >= definition.minimum_samples
            ):
                raise GoalInputError("Эта цель уже выполнена текущими показателями")

            existing = next((row for row in rows if row.metric == metric.value), None)
            active_other = sum(
                row.completed_at is None and row.metric != metric.value for row in rows
            )
            if existing is None and active_other >= self.max_active_goals:
                raise GoalLimitError(
                    f"Одновременно можно держать не больше {self.max_active_goals} целей"
                )

            created = existing is None
            if existing is None:
                existing = PvPSeasonGoalRow(
                    user_id=user.user_id,
                    season=normalized_season,
                    metric=metric.value,
                    baseline_value=snapshot.value,
                    target_value=target,
                    completed_at=None,
                    created_at=reference,
                    updated_at=reference,
                )
                db.add(existing)
            else:
                existing.baseline_value = snapshot.value
                existing.target_value = target
                existing.completed_at = None
                existing.created_at = reference
                existing.updated_at = reference
            await db.flush()
            view = self._view(existing, snapshot)

        return GoalSetResult(created=created, goal=view)

    async def delete_goal(self, user_id: int, season: str, metric_raw: str) -> bool:
        normalized_season = self._normalize_season(season)
        metric = parse_metric(metric_raw)
        async with self.sessions.begin() as db:
            row = await db.get(
                PvPSeasonGoalRow,
                {
                    "user_id": user_id,
                    "season": normalized_season,
                    "metric": metric.value,
                },
                with_for_update=True,
            )
            if row is None:
                return False
            await db.delete(row)
        return True

    async def suggestions(self, user_id: int, season: str) -> tuple[GoalSuggestion, ...]:
        normalized_season = self._normalize_season(season)
        async with self.sessions() as db:
            snapshots = await self._snapshots(db, user_id, normalized_season)
            active_metrics = set(
                await db.scalars(
                    select(PvPSeasonGoalRow.metric).where(
                        PvPSeasonGoalRow.user_id == user_id,
                        PvPSeasonGoalRow.season == normalized_season,
                        PvPSeasonGoalRow.completed_at.is_(None),
                    )
                )
            )

        candidates: list[GoalSuggestion] = []
        matches = snapshots[GoalMetric.MATCHES]
        elo = snapshots[GoalMetric.ELO]
        if matches.value < self.placement_games:
            candidates.append(
                GoalSuggestion(
                    metric=GoalMetric.MATCHES,
                    target_value=float(self.placement_games),
                    reason="завершить рейтинговую калибровку",
                )
            )
        else:
            next_league = next(
                (
                    league
                    for league in LEAGUE_CATALOG
                    if league.minimum_rating > elo.value
                ),
                None,
            )
            if next_league is not None:
                candidates.append(
                    GoalSuggestion(
                        metric=GoalMetric.LEAGUE,
                        target_value=float(next_league.minimum_rating),
                        reason="подняться в следующий дивизион",
                    )
                )

        candidates.append(
            GoalSuggestion(
                metric=GoalMetric.WINS,
                target_value=snapshots[GoalMetric.WINS].value + 5,
                reason="набрать ещё пять побед в сезоне",
            )
        )
        candidates.append(
            GoalSuggestion(
                metric=GoalMetric.STREAK,
                target_value=max(2.0, snapshots[GoalMetric.STREAK].value + 2),
                reason="улучшить лучшую серию побед",
            )
        )

        skill_metrics = (GoalMetric.LOGIC, GoalMetric.EVIDENCE, GoalMetric.REBUTTAL)
        weakest = min(skill_metrics, key=lambda item: (snapshots[item].value, item.value))
        weakest_snapshot = snapshots[weakest]
        skill_target = min(10.0, max(7.0, round(weakest_snapshot.value + 0.5, 1)))
        if skill_target > weakest_snapshot.value:
            candidates.append(
                GoalSuggestion(
                    metric=weakest,
                    target_value=skill_target,
                    reason="подтянуть самый слабый судейский навык",
                )
            )

        result: list[GoalSuggestion] = []
        seen: set[GoalMetric] = set()
        for candidate in candidates:
            if candidate.metric.value in active_metrics or candidate.metric in seen:
                continue
            result.append(candidate)
            seen.add(candidate.metric)
            if len(result) == 3:
                break
        return tuple(result)

    async def delete_user_data(self, user_id: int) -> None:
        async with self.sessions.begin() as db:
            await db.execute(
                delete(PvPSeasonGoalRow).where(PvPSeasonGoalRow.user_id == user_id)
            )

    def _refresh_rows(
        self,
        rows: list[PvPSeasonGoalRow],
        snapshots: dict[GoalMetric, MetricSnapshot],
        reference: datetime,
    ) -> list[SeasonGoalView]:
        views: list[SeasonGoalView] = []
        for row in rows:
            try:
                metric = GoalMetric(row.metric)
            except ValueError:
                continue
            snapshot = snapshots[metric]
            definition = definition_for(metric)
            if (
                row.completed_at is None
                and snapshot.samples >= definition.minimum_samples
                and snapshot.value >= row.target_value
            ):
                row.completed_at = reference
                row.updated_at = reference
            views.append(self._view(row, snapshot))
        return views

    @staticmethod
    def _view(row: PvPSeasonGoalRow, snapshot: MetricSnapshot) -> SeasonGoalView:
        return SeasonGoalView(
            metric=snapshot.metric,
            baseline_value=row.baseline_value,
            target_value=row.target_value,
            current_value=snapshot.value,
            samples=snapshot.samples,
            completed_at=row.completed_at,
            created_at=row.created_at,
        )

    async def _snapshots(
        self,
        db: AsyncSession,
        user_id: int,
        season: str,
    ) -> dict[GoalMetric, MetricSnapshot]:
        player = await db.get(PvPPlayerRow, {"user_id": user_id, "season": season})
        matches = list(
            await db.scalars(
                select(PvPMatchRow)
                .where(
                    PvPMatchRow.season == season,
                    or_(
                        PvPMatchRow.pro_user_id == user_id,
                        PvPMatchRow.con_user_id == user_id,
                    ),
                )
                .order_by(PvPMatchRow.ended_at.asc(), PvPMatchRow.match_id.asc())
            )
        )
        rating = float(player.rating if player is not None else 1_000)
        games = int(player.games if player is not None else len(matches))
        wins = int(
            player.wins
            if player is not None
            else sum(match.winner_user_id == user_id for match in matches)
        )
        win_rate = 0.0 if games == 0 else wins * 100 / games

        current_streak = 0
        best_streak = 0
        skill_values: dict[GoalMetric, list[float]] = defaultdict(list)
        for match in matches:
            if match.winner_user_id == user_id:
                current_streak += 1
                best_streak = max(best_streak, current_streak)
            else:
                current_streak = 0
            raw_scores = (
                match.pro_scores if match.pro_user_id == user_id else match.con_scores
            )
            parsed = self._parse_scores(raw_scores)
            if parsed is None:
                continue
            for metric, value in parsed.items():
                skill_values[metric].append(value)

        snapshots = {
            GoalMetric.ELO: MetricSnapshot(GoalMetric.ELO, rating, games),
            GoalMetric.LEAGUE: MetricSnapshot(GoalMetric.LEAGUE, rating, games),
            GoalMetric.WINS: MetricSnapshot(GoalMetric.WINS, float(wins), games),
            GoalMetric.MATCHES: MetricSnapshot(GoalMetric.MATCHES, float(games), games),
            GoalMetric.WIN_RATE: MetricSnapshot(GoalMetric.WIN_RATE, win_rate, games),
            GoalMetric.STREAK: MetricSnapshot(
                GoalMetric.STREAK,
                float(best_streak),
                games,
            ),
        }
        for metric in (GoalMetric.LOGIC, GoalMetric.EVIDENCE, GoalMetric.REBUTTAL):
            values = skill_values[metric]
            snapshots[metric] = MetricSnapshot(
                metric=metric,
                value=fmean(values) if values else 0.0,
                samples=len(values),
            )
        return snapshots

    @staticmethod
    def _parse_scores(raw: object) -> dict[GoalMetric, float] | None:
        if not isinstance(raw, dict):
            return None
        result: dict[GoalMetric, float] = {}
        for metric in (GoalMetric.LOGIC, GoalMetric.EVIDENCE, GoalMetric.REBUTTAL):
            value = raw.get(metric.value)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return None
            normalized = float(value)
            if not 0 <= normalized <= 10:
                return None
            result[metric] = normalized
        return result

    @staticmethod
    def _normalize_season(season: str) -> str:
        normalized = season.strip()
        if not normalized or len(normalized) > 32:
            raise GoalInputError("Некорректный идентификатор сезона")
        return normalized
