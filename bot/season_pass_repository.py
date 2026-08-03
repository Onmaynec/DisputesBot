from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .cosmetic_database import PvPCosmeticLoadoutRow, PvPCosmeticRow
from .cosmetics import SEASON_PASS_COMPLETION_COSMETIC, CosmeticKind
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
            completion_cosmetic_owned = (
                await db.scalar(
                    select(PvPCosmeticRow.item_id)
                    .where(
                        PvPCosmeticRow.user_id == user_id,
                        PvPCosmeticRow.season == normalized_season,
                        PvPCosmeticRow.item_id
                        == SEASON_PASS_COMPLETION_COSMETIC.item_id,
                    )
                    .limit(1)
                )
                is not None
            )
        season_points = int(wallet.season_points if wallet is not None else 0)
        wallet_tokens = int(wallet.tokens if wallet is not None else 0)
        claim_by_tier = {row.tier_id: row for row in claims}
        views: list[SeasonPassTierView] = []
        for tier in SEASON_PASS_TIERS:
            row = claim_by_tier.get(tier.tier_id)
            cosmetic_granted_at = None
            if row is not None and row.reward_item_id == tier.reward_cosmetic_id:
                cosmetic_granted_at = row.cosmetic_granted_at
            views.append(
                SeasonPassTierView(
                    tier=tier,
                    season_points=season_points,
                    claimed_at=row.claimed_at if row is not None else None,
                    cosmetic_granted_at=cosmetic_granted_at,
                )
            )
        return SeasonPassDashboard(
            user_id=user_id,
            season=normalized_season,
            season_points=season_points,
            wallet_tokens=wallet_tokens,
            tiers=tuple(views),
            completion_cosmetic_owned=completion_cosmetic_owned,
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

            claim_rows = list(
                await db.scalars(
                    select(PvPSeasonPassClaimRow)
                    .where(
                        PvPSeasonPassClaimRow.user_id == user.user_id,
                        PvPSeasonPassClaimRow.season == normalized_season,
                    )
                    .with_for_update()
                )
            )
            claim_by_tier = {row.tier_id: row for row in claim_rows}
            owned_ids = set(
                await db.scalars(
                    select(PvPCosmeticRow.item_id)
                    .where(
                        PvPCosmeticRow.user_id == user.user_id,
                        PvPCosmeticRow.season == normalized_season,
                    )
                    .with_for_update()
                )
            )
            loadout = await db.get(
                PvPCosmeticLoadoutRow,
                {"user_id": user.user_id, "season": normalized_season},
                with_for_update=True,
            )

            claimed_tier_ids: list[str] = []
            granted_cosmetic_ids: list[str] = []
            auto_equipped_ids: list[str] = []
            gained_tokens = 0

            for tier in SEASON_PASS_TIERS:
                if tier.points_required > wallet.season_points:
                    continue

                row = claim_by_tier.get(tier.tier_id)
                if row is None:
                    row = PvPSeasonPassClaimRow(
                        user_id=user.user_id,
                        season=normalized_season,
                        tier_id=tier.tier_id,
                        points_required=tier.points_required,
                        reward_tokens=tier.reward_tokens,
                        claimed_points=wallet.season_points,
                        claimed_at=reference,
                    )
                    db.add(row)
                    claim_by_tier[tier.tier_id] = row
                    claimed_tier_ids.append(tier.tier_id)
                    gained_tokens += tier.reward_tokens

                cosmetic_pending = (
                    row.reward_item_id != tier.reward_cosmetic_id
                    or row.cosmetic_granted_at is None
                )
                if not cosmetic_pending:
                    continue

                item = tier.reward_cosmetic
                if item.item_id not in owned_ids:
                    db.add(
                        PvPCosmeticRow(
                            user_id=user.user_id,
                            season=normalized_season,
                            item_id=item.item_id,
                            kind=item.kind.value,
                            purchased_at=reference,
                        )
                    )
                    owned_ids.add(item.item_id)
                    granted_cosmetic_ids.append(item.item_id)

                    if loadout is None:
                        loadout = PvPCosmeticLoadoutRow(
                            user_id=user.user_id,
                            season=normalized_season,
                        )
                        db.add(loadout)
                    if item.kind is CosmeticKind.TITLE and loadout.title_id is None:
                        loadout.title_id = item.item_id
                        loadout.updated_at = reference
                        auto_equipped_ids.append(item.item_id)
                    elif item.kind is CosmeticKind.BADGE and loadout.badge_id is None:
                        loadout.badge_id = item.item_id
                        loadout.updated_at = reference
                        auto_equipped_ids.append(item.item_id)

                row.reward_item_id = item.item_id
                row.cosmetic_granted_at = reference

            pass_complete = True
            for tier in SEASON_PASS_TIERS:
                row = claim_by_tier.get(tier.tier_id)
                if (
                    row is None
                    or row.reward_item_id != tier.reward_cosmetic_id
                    or row.cosmetic_granted_at is None
                    or tier.reward_cosmetic_id not in owned_ids
                ):
                    pass_complete = False
                    break

            completion_item = SEASON_PASS_COMPLETION_COSMETIC
            if pass_complete and completion_item.item_id not in owned_ids:
                db.add(
                    PvPCosmeticRow(
                        user_id=user.user_id,
                        season=normalized_season,
                        item_id=completion_item.item_id,
                        kind=completion_item.kind.value,
                        purchased_at=reference,
                    )
                )
                owned_ids.add(completion_item.item_id)
                granted_cosmetic_ids.append(completion_item.item_id)
                if loadout is None:
                    loadout = PvPCosmeticLoadoutRow(
                        user_id=user.user_id,
                        season=normalized_season,
                    )
                    db.add(loadout)
                if completion_item.kind is CosmeticKind.TITLE and loadout.title_id is None:
                    loadout.title_id = completion_item.item_id
                    loadout.updated_at = reference
                    auto_equipped_ids.append(completion_item.item_id)
                elif completion_item.kind is CosmeticKind.BADGE and loadout.badge_id is None:
                    loadout.badge_id = completion_item.item_id
                    loadout.updated_at = reference
                    auto_equipped_ids.append(completion_item.item_id)

            if gained_tokens:
                wallet.tokens += gained_tokens
                wallet.updated_at = reference
            if claimed_tier_ids or granted_cosmetic_ids:
                await db.flush()

            return SeasonPassClaimResult(
                claimed_tier_ids=tuple(claimed_tier_ids),
                granted_cosmetic_ids=tuple(granted_cosmetic_ids),
                auto_equipped_ids=tuple(auto_equipped_ids),
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
