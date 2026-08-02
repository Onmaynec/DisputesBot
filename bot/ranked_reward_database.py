from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class PvPRankedRewardClaimRow(Base):
    __tablename__ = "pvp_ranked_reward_claims"

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("user_profiles.user_id", ondelete="CASCADE"),
        primary_key=True,
        autoincrement=False,
    )
    season: Mapped[str] = mapped_column(String(32), primary_key=True)
    league_id: Mapped[str] = mapped_column(String(24), primary_key=True)
    reward_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    claimed_rating: Mapped[int] = mapped_column(Integer, nullable=False)
    claimed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )


Index(
    "ix_pvp_ranked_reward_claims_season_league",
    PvPRankedRewardClaimRow.season,
    PvPRankedRewardClaimRow.league_id,
)
