from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .cosmetic_database import PvPCosmeticLoadoutRow
from .cosmetics import cosmetic_by_id
from .database import (
    PvPBlockRow,
    PvPMatchRow,
    PvPPlayerRow,
    PvPProgressionRow,
    UserProfileRow,
)
from .pvp_models import PvPUser
from .social_database import PvPProfileSettingRow
from .social_models import (
    HeadToHeadView,
    ProfileLookupResult,
    ProfileLookupStatus,
    ProfileVisibility,
    RivalSummary,
    SocialProfileCard,
)


class SocialRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def visibility(self, user_id: int) -> ProfileVisibility:
        async with self.sessions() as db:
            row = await db.get(PvPProfileSettingRow, user_id)
        if row is not None and row.is_public:
            return ProfileVisibility.PUBLIC
        return ProfileVisibility.PRIVATE

    async def set_visibility(
        self,
        user: PvPUser,
        visibility: ProfileVisibility,
        *,
        now: datetime | None = None,
    ) -> ProfileVisibility:
        reference = now or datetime.now(UTC)
        async with self.sessions.begin() as db:
            await self._ensure_profile(db, user, reference)
            row = await db.get(PvPProfileSettingRow, user.user_id, with_for_update=True)
            if row is None:
                row = PvPProfileSettingRow(
                    user_id=user.user_id,
                    is_public=visibility is ProfileVisibility.PUBLIC,
                    updated_at=reference,
                )
                db.add(row)
            else:
                row.is_public = visibility is ProfileVisibility.PUBLIC
                row.updated_at = reference
        return visibility

    async def profile(
        self,
        requester: PvPUser,
        target_id: int,
        season: str,
    ) -> ProfileLookupResult:
        async with self.sessions.begin() as db:
            if requester.user_id == target_id:
                await self._ensure_profile(db, requester, datetime.now(UTC))
            target = await db.get(UserProfileRow, target_id)
            if target is None:
                return ProfileLookupResult(ProfileLookupStatus.NOT_FOUND, None)

            setting = await db.get(PvPProfileSettingRow, target_id)
            is_public = bool(setting is not None and setting.is_public)
            if requester.user_id != target_id:
                if await self._blocked(db, requester.user_id, target_id):
                    return ProfileLookupResult(ProfileLookupStatus.BLOCKED, None)
                if not is_public:
                    return ProfileLookupResult(ProfileLookupStatus.PRIVATE, None)

            player = await db.get(
                PvPPlayerRow,
                {"user_id": target_id, "season": season},
            )
            wallet = await db.get(
                PvPProgressionRow,
                {"user_id": target_id, "season": season},
            )
            loadout = await db.get(
                PvPCosmeticLoadoutRow,
                {"user_id": target_id, "season": season},
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

        rank = ranked_ids.index(target_id) + 1 if target_id in ranked_ids else None
        return ProfileLookupResult(
            ProfileLookupStatus.FOUND,
            SocialProfileCard(
                user_id=target_id,
                display_name=target.display_name,
                username=target.username,
                season=season,
                rating=player.rating if player is not None else None,
                rank=rank,
                games=player.games if player is not None else 0,
                wins=player.wins if player is not None else 0,
                draws=player.draws if player is not None else 0,
                losses=player.losses if player is not None else 0,
                season_points=wallet.season_points if wallet is not None else 0,
                tokens=wallet.tokens if wallet is not None else 0,
                title=cosmetic_by_id(loadout.title_id if loadout is not None else None),
                badge=cosmetic_by_id(loadout.badge_id if loadout is not None else None),
                is_public=is_public,
            ),
        )

    async def rivals(
        self,
        user_id: int,
        season: str,
        *,
        limit: int = 5,
    ) -> list[RivalSummary]:
        async with self.sessions() as db:
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
            opponent_ids = {
                row.con_user_id if row.pro_user_id == user_id else row.pro_user_id
                for row in matches
            }
            profiles = {
                row.user_id: row
                for row in (
                    await db.scalars(
                        select(UserProfileRow).where(UserProfileRow.user_id.in_(opponent_ids))
                    )
                ).all()
            }

        aggregates: dict[int, dict[str, int | datetime]] = {}
        for row in matches:
            opponent_id = (
                row.con_user_id if row.pro_user_id == user_id else row.pro_user_id
            )
            data = aggregates.setdefault(
                opponent_id,
                {
                    "matches": 0,
                    "wins": 0,
                    "draws": 0,
                    "losses": 0,
                    "rated_matches": 0,
                    "rating_delta": 0,
                    "last_played_at": row.ended_at,
                },
            )
            data["matches"] = int(data["matches"]) + 1
            data["rated_matches"] = int(data["rated_matches"]) + int(row.rated)
            if row.winner_user_id == user_id:
                data["wins"] = int(data["wins"]) + 1
            elif row.winner_user_id is None:
                data["draws"] = int(data["draws"]) + 1
            else:
                data["losses"] = int(data["losses"]) + 1
            if row.rated:
                before = (
                    row.pro_rating_before
                    if row.pro_user_id == user_id
                    else row.con_rating_before
                )
                after = (
                    row.pro_rating_after
                    if row.pro_user_id == user_id
                    else row.con_rating_after
                )
                data["rating_delta"] = int(data["rating_delta"]) + after - before
            data["last_played_at"] = row.ended_at

        results = []
        for opponent_id, data in aggregates.items():
            profile = profiles.get(opponent_id)
            results.append(
                RivalSummary(
                    opponent_id=opponent_id,
                    display_name=(
                        profile.display_name if profile is not None else f"Игрок {opponent_id}"
                    ),
                    username=profile.username if profile is not None else None,
                    matches=int(data["matches"]),
                    wins=int(data["wins"]),
                    draws=int(data["draws"]),
                    losses=int(data["losses"]),
                    rated_matches=int(data["rated_matches"]),
                    rating_delta=int(data["rating_delta"]),
                    last_played_at=data["last_played_at"],
                )
            )
        results.sort(
            key=lambda item: (-item.matches, -item.last_played_at.timestamp(), item.opponent_id)
        )
        return results[: max(1, min(limit, 20))]

    async def head_to_head(
        self,
        user_id: int,
        opponent_id: int,
        season: str,
    ) -> HeadToHeadView | None:
        if user_id == opponent_id:
            return None
        async with self.sessions() as db:
            matches = list(
                await db.scalars(
                    select(PvPMatchRow)
                    .where(
                        PvPMatchRow.season == season,
                        or_(
                            (
                                (PvPMatchRow.pro_user_id == user_id)
                                & (PvPMatchRow.con_user_id == opponent_id)
                            ),
                            (
                                (PvPMatchRow.pro_user_id == opponent_id)
                                & (PvPMatchRow.con_user_id == user_id)
                            ),
                        ),
                    )
                    .order_by(PvPMatchRow.ended_at.asc(), PvPMatchRow.match_id.asc())
                )
            )
            profile = await db.get(UserProfileRow, opponent_id)
        if not matches:
            return None

        wins = sum(row.winner_user_id == user_id for row in matches)
        draws = sum(row.winner_user_id is None for row in matches)
        losses = len(matches) - wins - draws
        rating_delta = 0
        current_win_streak = 0
        for row in matches:
            if row.rated:
                before = (
                    row.pro_rating_before
                    if row.pro_user_id == user_id
                    else row.con_rating_before
                )
                after = (
                    row.pro_rating_after
                    if row.pro_user_id == user_id
                    else row.con_rating_after
                )
                rating_delta += after - before
            if row.winner_user_id == user_id:
                current_win_streak += 1
            else:
                current_win_streak = 0
        return HeadToHeadView(
            opponent_id=opponent_id,
            display_name=(
                profile.display_name if profile is not None else f"Игрок {opponent_id}"
            ),
            username=profile.username if profile is not None else None,
            season=season,
            matches=len(matches),
            wins=wins,
            draws=draws,
            losses=losses,
            rated_matches=sum(row.rated for row in matches),
            rating_delta=rating_delta,
            current_win_streak=current_win_streak,
            last_played_at=matches[-1].ended_at,
            recent_topics=tuple(row.topic for row in reversed(matches[-3:])),
        )

    async def delete_user_data(self, user_id: int) -> None:
        async with self.sessions.begin() as db:
            await db.execute(
                delete(PvPProfileSettingRow).where(
                    PvPProfileSettingRow.user_id == user_id
                )
            )

    @staticmethod
    async def _blocked(db: AsyncSession, first_id: int, second_id: int) -> bool:
        value = await db.scalar(
            select(PvPBlockRow.blocker_id)
            .where(
                or_(
                    (
                        (PvPBlockRow.blocker_id == first_id)
                        & (PvPBlockRow.blocked_id == second_id)
                    ),
                    (
                        (PvPBlockRow.blocker_id == second_id)
                        & (PvPBlockRow.blocked_id == first_id)
                    ),
                )
            )
            .limit(1)
        )
        return value is not None

    @staticmethod
    async def _ensure_profile(
        db: AsyncSession,
        user: PvPUser,
        now: datetime,
    ) -> UserProfileRow:
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
            profile.updated_at = now
        return profile
