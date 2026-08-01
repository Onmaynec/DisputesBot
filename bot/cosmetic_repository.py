from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .cosmetic_database import PvPCosmeticLoadoutRow, PvPCosmeticRow
from .cosmetics import (
    CosmeticInventoryView,
    CosmeticKind,
    EquipResult,
    EquipStatus,
    PurchaseResult,
    PurchaseStatus,
    PvPProfileCard,
    cosmetic_by_id,
)
from .database import PvPPlayerRow, PvPProgressionRow, UserProfileRow
from .pvp_models import PvPUser


class CosmeticRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def inventory(self, user_id: int, season: str) -> CosmeticInventoryView:
        async with self.sessions() as db:
            wallet = await db.get(
                PvPProgressionRow,
                {"user_id": user_id, "season": season},
            )
            loadout = await db.get(
                PvPCosmeticLoadoutRow,
                {"user_id": user_id, "season": season},
            )
            owned = frozenset(
                await db.scalars(
                    select(PvPCosmeticRow.item_id).where(
                        PvPCosmeticRow.user_id == user_id,
                        PvPCosmeticRow.season == season,
                    )
                )
            )
        return CosmeticInventoryView(
            season=season,
            tokens=wallet.tokens if wallet is not None else 0,
            season_points=wallet.season_points if wallet is not None else 0,
            owned_item_ids=owned,
            equipped_title_id=loadout.title_id if loadout is not None else None,
            equipped_badge_id=loadout.badge_id if loadout is not None else None,
        )

    async def purchase(
        self,
        user: PvPUser,
        season: str,
        item_id: str,
        *,
        now: datetime | None = None,
    ) -> PurchaseResult:
        item = cosmetic_by_id(item_id)
        if item is None:
            return PurchaseResult(
                status=PurchaseStatus.UNKNOWN_ITEM,
                item=None,
                tokens=0,
                season_points=0,
            )
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
                {"user_id": user.user_id, "season": season},
                with_for_update=True,
            )
            if wallet is None:
                wallet = PvPProgressionRow(user_id=user.user_id, season=season)
                db.add(wallet)
                await db.flush()

            owned = await db.get(
                PvPCosmeticRow,
                {"user_id": user.user_id, "season": season, "item_id": item.item_id},
            )
            if owned is not None:
                return PurchaseResult(
                    status=PurchaseStatus.ALREADY_OWNED,
                    item=item,
                    tokens=wallet.tokens,
                    season_points=wallet.season_points,
                )
            if wallet.season_points < item.required_points:
                return PurchaseResult(
                    status=PurchaseStatus.LOCKED,
                    item=item,
                    tokens=wallet.tokens,
                    season_points=wallet.season_points,
                )
            if wallet.tokens < item.price_tokens:
                return PurchaseResult(
                    status=PurchaseStatus.INSUFFICIENT_TOKENS,
                    item=item,
                    tokens=wallet.tokens,
                    season_points=wallet.season_points,
                )

            wallet.tokens -= item.price_tokens
            wallet.updated_at = reference
            db.add(
                PvPCosmeticRow(
                    user_id=user.user_id,
                    season=season,
                    item_id=item.item_id,
                    kind=item.kind.value,
                    purchased_at=reference,
                )
            )
            loadout = await db.get(
                PvPCosmeticLoadoutRow,
                {"user_id": user.user_id, "season": season},
                with_for_update=True,
            )
            if loadout is None:
                loadout = PvPCosmeticLoadoutRow(user_id=user.user_id, season=season)
                db.add(loadout)
            auto_equipped = False
            if item.kind is CosmeticKind.TITLE and loadout.title_id is None:
                loadout.title_id = item.item_id
                auto_equipped = True
            elif item.kind is CosmeticKind.BADGE and loadout.badge_id is None:
                loadout.badge_id = item.item_id
                auto_equipped = True
            loadout.updated_at = reference
            await db.flush()
            return PurchaseResult(
                status=PurchaseStatus.PURCHASED,
                item=item,
                tokens=wallet.tokens,
                season_points=wallet.season_points,
                auto_equipped=auto_equipped,
            )

    async def equip(self, user_id: int, season: str, item_id: str) -> EquipResult:
        item = cosmetic_by_id(item_id)
        if item is None:
            return EquipResult(status=EquipStatus.UNKNOWN_ITEM, item=None)
        async with self.sessions.begin() as db:
            owned = await db.get(
                PvPCosmeticRow,
                {"user_id": user_id, "season": season, "item_id": item.item_id},
            )
            if owned is None:
                return EquipResult(status=EquipStatus.NOT_OWNED, item=item)
            loadout = await db.get(
                PvPCosmeticLoadoutRow,
                {"user_id": user_id, "season": season},
                with_for_update=True,
            )
            if loadout is None:
                loadout = PvPCosmeticLoadoutRow(user_id=user_id, season=season)
                db.add(loadout)
            if item.kind is CosmeticKind.TITLE:
                loadout.title_id = item.item_id
            else:
                loadout.badge_id = item.item_id
            loadout.updated_at = datetime.now(UTC)
            await db.flush()
        return EquipResult(status=EquipStatus.EQUIPPED, item=item)

    async def unequip(
        self,
        user_id: int,
        season: str,
        kind: CosmeticKind,
    ) -> EquipResult:
        async with self.sessions.begin() as db:
            loadout = await db.get(
                PvPCosmeticLoadoutRow,
                {"user_id": user_id, "season": season},
                with_for_update=True,
            )
            if loadout is None:
                return EquipResult(status=EquipStatus.EMPTY_INVENTORY, item=None)
            previous_id = loadout.title_id if kind is CosmeticKind.TITLE else loadout.badge_id
            previous = cosmetic_by_id(previous_id)
            if kind is CosmeticKind.TITLE:
                loadout.title_id = None
            else:
                loadout.badge_id = None
            loadout.updated_at = datetime.now(UTC)
            await db.flush()
        return EquipResult(status=EquipStatus.EQUIPPED, item=previous)

    async def profile(self, user: PvPUser, season: str) -> PvPProfileCard:
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

            player = await db.get(
                PvPPlayerRow,
                {"user_id": user.user_id, "season": season},
            )
            wallet = await db.get(
                PvPProgressionRow,
                {"user_id": user.user_id, "season": season},
            )
            loadout = await db.get(
                PvPCosmeticLoadoutRow,
                {"user_id": user.user_id, "season": season},
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
        rank = ranked_ids.index(user.user_id) + 1 if user.user_id in ranked_ids else None
        return PvPProfileCard(
            user_id=user.user_id,
            display_name=profile.display_name,
            username=profile.username,
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
        )

    async def delete_user_data(self, user_id: int) -> None:
        async with self.sessions.begin() as db:
            await db.execute(
                delete(PvPCosmeticLoadoutRow).where(
                    PvPCosmeticLoadoutRow.user_id == user_id
                )
            )
            await db.execute(
                delete(PvPCosmeticRow).where(PvPCosmeticRow.user_id == user_id)
            )
