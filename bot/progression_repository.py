from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .database import (
    PvPDailyClaimRow,
    PvPMatchRow,
    PvPPlayerRow,
    PvPProgressionRow,
    UserProfileRow,
)
from .progression_models import (
    DailyClaimResult,
    DailyMetrics,
    DailyProgressView,
    DailyQuestProgress,
    ProgressionWalletView,
    PvPAnalytics,
    SeasonStanding,
    daily_quests,
    progression_day,
    progression_window,
    quest_progress,
)
from .pvp_models import PvPUser


class ProgressionRepository:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        *,
        reset_hour_utc: int = 0,
        reward_multiplier: int = 1,
        stats_window_days: int = 30,
    ) -> None:
        if not 0 <= reset_hour_utc <= 23:
            raise ValueError("reset_hour_utc must be between 0 and 23")
        if not 1 <= reward_multiplier <= 10:
            raise ValueError("reward_multiplier must be between 1 and 10")
        if not 1 <= stats_window_days <= 365:
            raise ValueError("stats_window_days must be between 1 and 365")
        self.sessions = sessions
        self.reset_hour_utc = reset_hour_utc
        self.reward_multiplier = reward_multiplier
        self.stats_window_days = stats_window_days

    async def daily_progress(
        self,
        user_id: int,
        season: str,
        *,
        now: datetime | None = None,
    ) -> DailyProgressView:
        reference = now or datetime.now(UTC)
        day = progression_day(reference, self.reset_hour_utc)
        start, end = progression_window(day, self.reset_hour_utc)
        async with self.sessions() as db:
            rows = await self._daily_matches(db, user_id, season, start, end)
            claimed = set(
                await db.scalars(
                    select(PvPDailyClaimRow.quest_id).where(
                        PvPDailyClaimRow.user_id == user_id,
                        PvPDailyClaimRow.season == season,
                        PvPDailyClaimRow.day == day,
                    )
                )
            )
            wallet = await db.get(
                PvPProgressionRow,
                {"user_id": user_id, "season": season},
            )
        metrics = self._metrics(rows, user_id)
        quests = tuple(
            DailyQuestProgress(
                definition=definition,
                progress=quest_progress(definition, metrics),
                claimed=definition.quest_id in claimed,
            )
            for definition in daily_quests(day)
        )
        return DailyProgressView(
            day=day,
            window_start=start,
            window_end=end,
            quests=quests,
            wallet=self._wallet_view(wallet, user_id, season),
        )

    async def claim_daily(
        self,
        user: PvPUser,
        season: str,
        *,
        now: datetime | None = None,
    ) -> DailyClaimResult:
        reference = now or datetime.now(UTC)
        day = progression_day(reference, self.reset_hour_utc)
        start, end = progression_window(day, self.reset_hour_utc)
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

            wallet = await db.get(
                PvPProgressionRow,
                {"user_id": user.user_id, "season": season},
                with_for_update=True,
            )
            if wallet is None:
                wallet = PvPProgressionRow(user_id=user.user_id, season=season)
                db.add(wallet)
                await db.flush()

            rows = await self._daily_matches(db, user.user_id, season, start, end)
            metrics = self._metrics(rows, user.user_id)
            claimed = set(
                await db.scalars(
                    select(PvPDailyClaimRow.quest_id).where(
                        PvPDailyClaimRow.user_id == user.user_id,
                        PvPDailyClaimRow.season == season,
                        PvPDailyClaimRow.day == day,
                    )
                )
            )
            completed = [
                definition
                for definition in daily_quests(day)
                if definition.quest_id not in claimed
                and quest_progress(definition, metrics) >= definition.target
            ]
            gained_tokens = sum(item.reward_tokens for item in completed)
            gained_points = sum(item.reward_points for item in completed)
            gained_tokens *= self.reward_multiplier
            gained_points *= self.reward_multiplier

            for definition in completed:
                db.add(
                    PvPDailyClaimRow(
                        user_id=user.user_id,
                        season=season,
                        day=day,
                        quest_id=definition.quest_id,
                        reward_tokens=definition.reward_tokens * self.reward_multiplier,
                        reward_points=definition.reward_points * self.reward_multiplier,
                        claimed_at=reference,
                    )
                )

            if completed:
                wallet.tokens += gained_tokens
                wallet.season_points += gained_points
                wallet.daily_claims += len(completed)
                if wallet.last_claim_date != day:
                    yesterday = day - timedelta(days=1)
                    if wallet.last_claim_date == yesterday:
                        wallet.current_daily_streak += 1
                    else:
                        wallet.current_daily_streak = 1
                    wallet.best_daily_streak = max(
                        wallet.best_daily_streak,
                        wallet.current_daily_streak,
                    )
                    wallet.last_claim_date = day
                wallet.updated_at = reference
                await db.flush()

            result = DailyClaimResult(
                claimed_quest_ids=tuple(item.quest_id for item in completed),
                gained_tokens=gained_tokens,
                gained_points=gained_points,
                wallet=self._wallet_view(wallet, user.user_id, season),
            )
        return result

    async def wallet(self, user_id: int, season: str) -> ProgressionWalletView:
        async with self.sessions() as db:
            row = await db.get(
                PvPProgressionRow,
                {"user_id": user_id, "season": season},
            )
        return self._wallet_view(row, user_id, season)

    async def top(self, season: str, *, limit: int = 10) -> list[SeasonStanding]:
        async with self.sessions() as db:
            rows = (
                await db.execute(
                    select(PvPProgressionRow, UserProfileRow)
                    .join(
                        UserProfileRow,
                        UserProfileRow.user_id == PvPProgressionRow.user_id,
                    )
                    .where(PvPProgressionRow.season == season)
                    .order_by(
                        PvPProgressionRow.season_points.desc(),
                        PvPProgressionRow.tokens.desc(),
                        PvPProgressionRow.updated_at.asc(),
                        PvPProgressionRow.user_id.asc(),
                    )
                    .limit(max(1, min(limit, 50)))
                )
            ).all()
        return [
            SeasonStanding(
                user_id=wallet.user_id,
                display_name=profile.display_name,
                username=profile.username,
                season=wallet.season,
                season_points=wallet.season_points,
                tokens=wallet.tokens,
                current_daily_streak=wallet.current_daily_streak,
            )
            for wallet, profile in rows
        ]

    async def analytics(
        self,
        user_id: int,
        season: str,
        *,
        now: datetime | None = None,
    ) -> PvPAnalytics:
        reference = now or datetime.now(UTC)
        async with self.sessions() as db:
            matches = (
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
            ).all()
            player = await db.get(
                PvPPlayerRow,
                {"user_id": user_id, "season": season},
            )
            ranked_ids = list(
                await db.scalars(
                    select(PvPPlayerRow.user_id)
                    .where(PvPPlayerRow.season == season)
                    .order_by(
                        PvPPlayerRow.rating.desc(),
                        PvPPlayerRow.games.desc(),
                        PvPPlayerRow.updated_at.asc(),
                        PvPPlayerRow.user_id.asc(),
                    )
                )
            )

        wins = sum(row.winner_user_id == user_id for row in matches)
        draws = sum(row.winner_user_id is None for row in matches)
        losses = len(matches) - wins - draws
        rated_matches = sum(row.rated for row in matches)
        unique_opponents = {
            row.con_user_id if row.pro_user_id == user_id else row.pro_user_id
            for row in matches
        }
        current_streak = 0
        best_streak = 0
        for row in matches:
            if row.winner_user_id == user_id:
                current_streak += 1
                best_streak = max(best_streak, current_streak)
            else:
                current_streak = 0

        cutoff = reference - timedelta(days=self.stats_window_days)
        rating_delta = 0
        for row in matches:
            if not row.rated or self._as_utc(row.ended_at) < cutoff:
                continue
            if row.pro_user_id == user_id:
                rating_delta += row.pro_rating_after - row.pro_rating_before
            else:
                rating_delta += row.con_rating_after - row.con_rating_before

        pro_matches = sum(row.pro_user_id == user_id for row in matches)
        con_matches = len(matches) - pro_matches
        pro_wins = sum(
            row.pro_user_id == user_id and row.winner_user_id == user_id
            for row in matches
        )
        con_wins = sum(
            row.con_user_id == user_id and row.winner_user_id == user_id
            for row in matches
        )
        rank = ranked_ids.index(user_id) + 1 if user_id in ranked_ids else None
        win_rate = round(wins * 100 / len(matches), 1) if matches else 0.0
        return PvPAnalytics(
            user_id=user_id,
            season=season,
            rating=player.rating if player is not None else None,
            rank=rank,
            total_matches=len(matches),
            rated_matches=rated_matches,
            unrated_matches=len(matches) - rated_matches,
            wins=wins,
            draws=draws,
            losses=losses,
            win_rate=win_rate,
            unique_opponents=len(unique_opponents),
            rating_delta_window=rating_delta,
            current_win_streak=current_streak,
            best_win_streak=best_streak,
            pro_matches=pro_matches,
            pro_wins=pro_wins,
            con_matches=con_matches,
            con_wins=con_wins,
            window_days=self.stats_window_days,
        )

    async def delete_user_data(self, user_id: int) -> None:
        async with self.sessions.begin() as db:
            await db.execute(
                delete(PvPDailyClaimRow).where(PvPDailyClaimRow.user_id == user_id)
            )
            await db.execute(
                delete(PvPProgressionRow).where(PvPProgressionRow.user_id == user_id)
            )

    @staticmethod
    async def _daily_matches(
        db: AsyncSession,
        user_id: int,
        season: str,
        start: datetime,
        end: datetime,
    ) -> list[PvPMatchRow]:
        return list(
            await db.scalars(
                select(PvPMatchRow).where(
                    PvPMatchRow.season == season,
                    PvPMatchRow.ended_at >= start,
                    PvPMatchRow.ended_at < end,
                    or_(
                        PvPMatchRow.pro_user_id == user_id,
                        PvPMatchRow.con_user_id == user_id,
                    ),
                )
            )
        )

    @staticmethod
    def _metrics(rows: list[PvPMatchRow], user_id: int) -> DailyMetrics:
        opponents = {
            row.con_user_id if row.pro_user_id == user_id else row.pro_user_id
            for row in rows
        }
        return DailyMetrics(
            matches=len(rows),
            wins=sum(row.winner_user_id == user_id for row in rows),
            rated_matches=sum(row.rated for row in rows),
            unique_opponents=len(opponents),
            rated_wins=sum(
                row.rated and row.winner_user_id == user_id for row in rows
            ),
        )

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @staticmethod
    def _wallet_view(
        row: PvPProgressionRow | None,
        user_id: int,
        season: str,
    ) -> ProgressionWalletView:
        if row is None:
            return ProgressionWalletView(
                user_id=user_id,
                season=season,
                tokens=0,
                season_points=0,
                daily_claims=0,
                current_daily_streak=0,
                best_daily_streak=0,
                last_claim_date=None,
            )
        return ProgressionWalletView(
            user_id=row.user_id,
            season=row.season,
            tokens=row.tokens,
            season_points=row.season_points,
            daily_claims=row.daily_claims,
            current_daily_streak=row.current_daily_streak,
            best_daily_streak=row.best_daily_streak,
            last_claim_date=row.last_claim_date,
        )
