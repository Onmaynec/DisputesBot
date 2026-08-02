from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .database import PvPProgressionRow, UserProfileRow
from .pvp_models import PvPUser
from .season_pass_database import PvPSeasonPassClaimRow
from .season_pass_models import (
    SEASON_PASS_TIERS,
    SeasonPassClaimResult,
    SeasonPassDashboard,
    SeasonPassInputError,
    SeasonPassTierView,
)


class SeasonPassRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def dashboard(self, user_id: int, season: str) -> SeasonPassDashboard:
        normalized_season = self._normalize_season(season)
        async with self.sessions() as db:
            wallet = await db.get(
                PvPProgressionRow,
                {"user_id": user_id, "season": normalized_season},
            )
            claims = list(
                await db.scalars(
                    select(PvPSeasonPassClaimRow).where(
                        PvPSeasonPassClaimRow.user_id == user_id,
                        PvPSeasonPassClaimRow.season == normalized_season,
                    )
                )
            )
        season_points = int(wallet.season_points if wallet is not None else 0)
        wallet_tokens = int(wallet.tokens if wallet is not None else 0)
        claimed_at = {row.tier_id: row.claimed_at for row in claims}
        return SeasonPassDashboard(
            user_id=user_id,
            season=normalized_season,
            season_points=season_points,
            wallet_tokens=wallet_tokens,
            tiers=tuple(
                SeasonPassTierView(
                    tier=tier,
                    season_points=season_points,
                    claimed_at=claimed_at.get(tier.tier_id),
                )
                for tier in SEASON_PASS_TIERS
            ),
        )

    async def claim(
        self,
        user: PvPUser,
        season: str,
        *,
        now: datetime | None = None,
    ) -> SeasonPassClaimResult:
        normalized_season = self._normalize_season(season)
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

            wallet = await db.get(
                PvPProgressionRow,
                {"user_id": user.user_id, "season": normalized_season},
                with_for_update=True,
            )
            if wallet is None:
                wallet = PvPProgressionRow(
                    user_id=user.user_id,
                    season=normalized_season,
                )
                db.add(wallet)
                await db.flush()

            claimed_ids = set(
                await db.scalars(
                    select(PvPSeasonPassClaimRow.tier_id)
                    .where(
                        PvPSeasonPassClaimRow.user_id == user.user_id,
                        PvPSeasonPassClaimRow.season == normalized_season,
                    )
                    .with_for_update()
                )
            )
            unlocked = tuple(
                tier
                for tier in SEASON_PASS_TIERS
                if tier.points_required <= wallet.season_points
                and tier.tier_id not in claimed_ids
            )
            gained_tokens = sum(tier.reward_tokens for tier in unlocked)
            for tier in unlocked:
                db.add(
                    PvPSeasonPassClaimRow(
                        user_id=user.user_id,
                        season=normalized_season,
                        tier_id=tier.tier_id,
                        points_required=tier.points_required,
                        reward_tokens=tier.reward_tokens,
                        claimed_points=wallet.season_points,
                        claimed_at=reference,
                    )
                )
            if gained_tokens:
                wallet.tokens += gained_tokens
                wallet.updated_at = reference
                await db.flush()

            return SeasonPassClaimResult(
                claimed_tier_ids=tuple(tier.tier_id for tier in unlocked),
                gained_tokens=gained_tokens,
                wallet_tokens=wallet.tokens,
                season_points=wallet.season_points,
            )

    async def delete_user_data(self, user_id: int) -> None:
        async with self.sessions.begin() as db:
            await db.execute(
                delete(PvPSeasonPassClaimRow).where(
                    PvPSeasonPassClaimRow.user_id == user_id
                )
            )

    @staticmethod
    def _normalize_season(season: str) -> str:
        normalized = season.strip()
        if not normalized or len(normalized) > 32:
            raise SeasonPassInputError("Некорректный идентификатор сезона")
        return normalized
