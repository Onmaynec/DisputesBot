from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class PvPCosmeticRow(Base):
    __tablename__ = "pvp_cosmetics"

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("user_profiles.user_id", ondelete="CASCADE"),
        primary_key=True,
        autoincrement=False,
    )
    season: Mapped[str] = mapped_column(String(32), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(48), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    purchased_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )


class PvPCosmeticLoadoutRow(Base):
    __tablename__ = "pvp_cosmetic_loadouts"

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("user_profiles.user_id", ondelete="CASCADE"),
        primary_key=True,
        autoincrement=False,
    )
    season: Mapped[str] = mapped_column(String(32), primary_key=True)
    title_id: Mapped[str | None] = mapped_column(String(48), nullable=True)
    badge_id: Mapped[str | None] = mapped_column(String(48), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


Index("ix_pvp_cosmetics_user_season", PvPCosmeticRow.user_id, PvPCosmeticRow.season)
Index("ix_pvp_cosmetics_season_item", PvPCosmeticRow.season, PvPCosmeticRow.item_id)
