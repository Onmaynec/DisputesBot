from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .cosmetics_models import (
    TITLE_CATALOG,
    EquipOutcome,
    PurchaseOutcome,
    TitleEquipResult,
    TitleInventoryView,
    TitlePurchaseResult,
    TitleShopEntry,
    TitleShopView,
    title_by_id,
)
from .database import (
    PvPProgressionRow,
    PvPTitleLoadoutRow,
    PvPTitlePurchaseRow,
    UserProfileRow,
)
from .pvp_models import PvPUser


class CosmeticsRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def shop(self, user_id: int, season: str) -> TitleShopView:
        async with self.sessions() as db:
            wallet = await db.get(
                PvPProgressionRow,
                {"user_id": user_id, "season": season},
            )
            owned_ids = set(
                await db.scalars(
                    select(PvPTitlePurchaseRow.title_id).where(
                        PvPTitlePurchaseRow.user_id == user_id,
                        PvPTitlePurchaseRow.season == season,
                    )
                )
            )
            loadout = await db.get(
                PvPTitleLoadoutRow,
                {"user_id": user_id, "season": season},
            )
        equipped_id = loadout.equipped_title_id if loadout is not None else None
        points = wallet.season_points if wallet is not None else 0
        return TitleShopView(
            season=season,
            tokens=wallet.tokens if wallet is not None else 0,
            season_points=points,
            entries=tuple(
                TitleShopEntry(
                    definition=definition,
                    owned=definition.title_id in owned_ids,
                    equipped=definition.title_id == equipped_id,
                    unlocked=points >= definition.minimum_points,
                )
                for definition in TITLE_CATALOG
            ),
        )

    async def inventory(self, user_id: int, season: str) -> TitleInventoryView:
        async with self.sessions() as db:
            wallet = await db.get(
                PvPProgressionRow,
                {"user_id": user_id, "season": season},
            )
            owned_ids = set(
                await db.scalars(
                    select(PvPTitlePurchaseRow.title_id).where(
                        PvPTitlePurchaseRow.user_id == user_id,
                        PvPTitlePurchaseRow.season == season,
                    )
                )
            )
            loadout = await db.get(
                PvPTitleLoadoutRow,
                {"user_id": user_id, "season": season},
            )
        owned = tuple(item for item in TITLE_CATALOG if item.title_id in owned_ids)
        equipped = title_by_id(loadout.equipped_title_id) if loadout is not None else None
        return TitleInventoryView(
            season=season,
            tokens=wallet.tokens if wallet is not None else 0,
            owned=owned,
            equipped=equipped,
        )

    async def purchase(
        self,
        user: PvPUser,
        season: str,
        title_id: str,
        *,
        now: datetime | None = None,
    ) -> TitlePurchaseResult:
        definition = title_by_id(title_id)
        if definition is None:
            tokens, points = await self._wallet_values(user.user_id, season)
            return TitlePurchaseResult(
                outcome=PurchaseOutcome.UNKNOWN_TITLE,
                definition=None,
                tokens=tokens,
                season_points=points,
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

            existing = await db.get(
                PvPTitlePurchaseRow,
                {
                    "user_id": user.user_id,
                    "season": season,
                    "title_id": definition.title_id,
                },
            )
            if existing is not None:
                return TitlePurchaseResult(
                    outcome=PurchaseOutcome.ALREADY_OWNED,
                    definition=definition,
                    tokens=wallet.tokens,
                    season_points=wallet.season_points,
                )
            if wallet.season_points < definition.minimum_points:
                return TitlePurchaseResult(
                    outcome=PurchaseOutcome.LOCKED,
                    definition=definition,
                    tokens=wallet.tokens,
                    season_points=wallet.season_points,
                )
            if wallet.tokens < definition.price_tokens:
                return TitlePurchaseResult(
                    outcome=PurchaseOutcome.INSUFFICIENT_TOKENS,
                    definition=definition,
                    tokens=wallet.tokens,
                    season_points=wallet.season_points,
                )

            wallet.tokens -= definition.price_tokens
            wallet.updated_at = reference
            db.add(
                PvPTitlePurchaseRow(
                    user_id=user.user_id,
                    season=season,
                    title_id=definition.title_id,
                    price_paid=definition.price_tokens,
                    purchased_at=reference,
                )
            )
            loadout = await db.get(
                PvPTitleLoadoutRow,
                {"user_id": user.user_id, "season": season},
                with_for_update=True,
            )
            auto_equipped = False
            if loadout is None:
                loadout = PvPTitleLoadoutRow(
                    user_id=user.user_id,
                    season=season,
                    equipped_title_id=definition.title_id,
                    updated_at=reference,
                )
                db.add(loadout)
                auto_equipped = True
            elif loadout.equipped_title_id is None:
                loadout.equipped_title_id = definition.title_id
                loadout.updated_at = reference
                auto_equipped = True
            await db.flush()
            return TitlePurchaseResult(
                outcome=PurchaseOutcome.PURCHASED,
                definition=definition,
                tokens=wallet.tokens,
                season_points=wallet.season_points,
                auto_equipped=auto_equipped,
            )

    async def equip(
        self,
        user_id: int,
        season: str,
        title_id: str,
        *,
        now: datetime | None = None,
    ) -> TitleEquipResult:
        normalized = title_id.strip().casefold()
        clear = normalized in {"none", "off", "clear", "нет", "снять"}
        definition = None if clear else title_by_id(normalized)
        if not clear and definition is None:
            return TitleEquipResult(EquipOutcome.UNKNOWN_TITLE, None)

        reference = now or datetime.now(UTC)
        async with self.sessions.begin() as db:
            profile = await db.get(UserProfileRow, user_id, with_for_update=True)
            if profile is None:
                if clear:
                    return TitleEquipResult(EquipOutcome.CLEARED, None)
                return TitleEquipResult(EquipOutcome.NOT_OWNED, definition)

            loadout = await db.get(
                PvPTitleLoadoutRow,
                {"user_id": user_id, "season": season},
                with_for_update=True,
            )
            if clear:
                if loadout is not None:
                    loadout.equipped_title_id = None
                    loadout.updated_at = reference
                return TitleEquipResult(EquipOutcome.CLEARED, None)

            purchase = await db.get(
                PvPTitlePurchaseRow,
                {
                    "user_id": user_id,
                    "season": season,
                    "title_id": definition.title_id,
                },
            )
            if purchase is None:
                return TitleEquipResult(EquipOutcome.NOT_OWNED, definition)
            if loadout is None:
                db.add(
                    PvPTitleLoadoutRow(
                        user_id=user_id,
                        season=season,
                        equipped_title_id=definition.title_id,
                        updated_at=reference,
                    )
                )
                return TitleEquipResult(EquipOutcome.EQUIPPED, definition)
            if loadout.equipped_title_id == definition.title_id:
                return TitleEquipResult(EquipOutcome.ALREADY_EQUIPPED, definition)
            loadout.equipped_title_id = definition.title_id
            loadout.updated_at = reference
            return TitleEquipResult(EquipOutcome.EQUIPPED, definition)

    async def equipped_title(self, user_id: int, season: str):
        async with self.sessions() as db:
            loadout = await db.get(
                PvPTitleLoadoutRow,
                {"user_id": user_id, "season": season},
            )
        return title_by_id(loadout.equipped_title_id) if loadout is not None else None

    async def delete_user_data(self, user_id: int) -> None:
        async with self.sessions.begin() as db:
            await db.execute(
                delete(PvPTitleLoadoutRow).where(PvPTitleLoadoutRow.user_id == user_id)
            )
            await db.execute(
                delete(PvPTitlePurchaseRow).where(PvPTitlePurchaseRow.user_id == user_id)
            )

    async def _wallet_values(self, user_id: int, season: str) -> tuple[int, int]:
        async with self.sessions() as db:
            wallet = await db.get(
                PvPProgressionRow,
                {"user_id": user_id, "season": season},
            )
        if wallet is None:
            return 0, 0
        return wallet.tokens, wallet.season_points
