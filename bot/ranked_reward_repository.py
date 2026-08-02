from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .database import PvPMatchRow, PvPPlayerRow, PvPProgressionRow, UserProfileRow
from .league_models import DEFAULT_PLACEMENT_GAMES, league_for_rating, league_status
from .pvp_models import PvPUser
from .ranked_reward_database import PvPRankedRewardClaimRow
from .ranked_reward_models import (
    RANKED_REWARD_CATALOG,
    RankedRewardClaimResult,
    RankedRewardEntry,
    RankedRewardsView,
    reward_definitions_up_to,
)


class RankedRewardRepository:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        *,
        placement_games: int = DEFAULT_PLACEMENT_GAMES,
    ) -> None:
        if placement_games < 0:
            raise ValueError("placement_games must not be negative")
        self.sessions = sessions
        self.placement_games = placement_games

    async def view(self, user_id: int, season: str) -> RankedRewardsView:
        async with self.sessions() as db:
            player = await db.get(PvPPlayerRow, {"user_id": user_id, "season": season})
            claimed = set(
                await db.scalars(
                    select(PvPRankedRewardClaimRow.league_id).where(
                        PvPRankedRewardClaimRow.user_id == user_id,
                        PvPRankedRewardClaimRow.season == season,
                    )
                )
            )
            wallet = await db.get(
                PvPProgressionRow,
                {"user_id": user_id, "season": season},
            )
            rating = player.rating if player is not None else 1000
            games = player.games if player is not None else 0
            peak_rating = await self._peak_rating(db, user_id, season, rating)
        return self._build_view(
            user_id=user_id,
            season=season,
            rating=rating,
            games=games,
            peak_rating=peak_rating,
            claimed=claimed,
            wallet_tokens=wallet.tokens if wallet is not None else 0,
        )

    async def claim(
        self,
        user: PvPUser,
        season: str,
        *,
        now: datetime | None = None,
    ) -> RankedRewardClaimResult:
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

            player = await db.get(
                PvPPlayerRow,
                {"user_id": user.user_id, "season": season},
                with_for_update=True,
            )
            claimed = set(
                await db.scalars(
                    select(PvPRankedRewardClaimRow.league_id).where(
                        PvPRankedRewardClaimRow.user_id == user.user_id,
                        PvPRankedRewardClaimRow.season == season,
                    )
                )
            )
            wallet = await db.get(
                PvPProgressionRow,
                {"user_id": user.user_id, "season": season},
                with_for_update=True,
            )

            rating = player.rating if player is not None else 1000
            games = player.games if player is not None else 0
            peak_rating = await self._peak_rating(db, user.user_id, season, rating)
            status = league_status(
                rating,
                games,
                placement_games=self.placement_games,
            )
            eligible = ()
            if not status.is_placement:
                eligible = reward_definitions_up_to(league_for_rating(peak_rating).league_id)
            new_rewards = tuple(
                definition
                for definition in eligible
                if definition.league.league_id.value not in claimed
            )
            gained_tokens = sum(definition.tokens for definition in new_rewards)

            if new_rewards and wallet is None:
                wallet = PvPProgressionRow(user_id=user.user_id, season=season)
                db.add(wallet)
                await db.flush()

            if wallet is not None and new_rewards:
                for definition in new_rewards:
                    db.add(
                        PvPRankedRewardClaimRow(
                            user_id=user.user_id,
                            season=season,
                            league_id=definition.league.league_id.value,
                            reward_tokens=definition.tokens,
                            claimed_rating=peak_rating,
                            claimed_at=reference,
                        )
                    )
                wallet.tokens += gained_tokens
                wallet.updated_at = reference
                claimed.update(
                    definition.league.league_id.value for definition in new_rewards
                )
                await db.flush()

            view = self._build_view(
                user_id=user.user_id,
                season=season,
                rating=rating,
                games=games,
                peak_rating=peak_rating,
                claimed=claimed,
                wallet_tokens=wallet.tokens if wallet is not None else 0,
            )
        return RankedRewardClaimResult(
            claimed_league_ids=tuple(
                definition.league.league_id for definition in new_rewards
            ),
            gained_tokens=gained_tokens,
            wallet_tokens=view.wallet_tokens,
            view=view,
        )

    async def delete_user_data(self, user_id: int) -> None:
        async with self.sessions.begin() as db:
            await db.execute(
                delete(PvPRankedRewardClaimRow).where(
                    PvPRankedRewardClaimRow.user_id == user_id
                )
            )

    async def _peak_rating(
        self,
        db: AsyncSession,
        user_id: int,
        season: str,
        current_rating: int,
    ) -> int:
        rows = (
            await db.execute(
                select(
                    PvPMatchRow.pro_user_id,
                    PvPMatchRow.con_user_id,
                    PvPMatchRow.pro_rating_after,
                    PvPMatchRow.con_rating_after,
                ).where(
                    PvPMatchRow.season == season,
                    or_(
                        PvPMatchRow.pro_user_id == user_id,
                        PvPMatchRow.con_user_id == user_id,
                    ),
                )
            )
        ).all()
        peak = max(1000, current_rating)
        for pro_user_id, _, pro_after, con_after in rows:
            peak = max(peak, pro_after if pro_user_id == user_id else con_after)
        return peak

    def _build_view(
        self,
        *,
        user_id: int,
        season: str,
        rating: int,
        games: int,
        peak_rating: int,
        claimed: set[str],
        wallet_tokens: int,
    ) -> RankedRewardsView:
        status = league_status(
            rating,
            games,
            placement_games=self.placement_games,
        )
        eligible_ids: set[str] = set()
        if not status.is_placement:
            eligible_ids = {
                definition.league.league_id.value
                for definition in reward_definitions_up_to(
                    league_for_rating(peak_rating).league_id
                )
            }
        entries = tuple(
            RankedRewardEntry(
                definition=definition,
                eligible=definition.league.league_id.value in eligible_ids,
                claimed=definition.league.league_id.value in claimed,
            )
            for definition in RANKED_REWARD_CATALOG
        )
        return RankedRewardsView(
            user_id=user_id,
            season=season,
            rating=rating,
            games=games,
            peak_rating=peak_rating,
            status=status,
            entries=entries,
            wallet_tokens=wallet_tokens,
        )
