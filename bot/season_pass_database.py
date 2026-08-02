from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class PvPSeasonPassClaimRow(Base):
    __tablename__ = "pvp_season_pass_claims"

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("user_profiles.user_id", ondelete="CASCADE"),
        primary_key=True,
        autoincrement=False,
    )
    season: Mapped[str] = mapped_column(String(32), primary_key=True)
    tier_id: Mapped[str] = mapped_column(String(24), primary_key=True)
    points_required: Mapped[int] = mapped_column(Integer, nullable=False)
    reward_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    claimed_points: Mapped[int] = mapped_column(Integer, nullable=False)
    claimed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )


Index(
    "ix_pvp_season_pass_claims_user_season_claimed",
    PvPSeasonPassClaimRow.user_id,
    PvPSeasonPassClaimRow.season,
    PvPSeasonPassClaimRow.claimed_at,
)
