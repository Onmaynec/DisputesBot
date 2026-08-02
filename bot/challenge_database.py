from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class PvPChallengeRow(Base):
    __tablename__ = "pvp_challenges"

    challenge_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    challenger_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("user_profiles.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    target_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("user_profiles.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    season: Mapped[str] = mapped_column(String(32), nullable=False)
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    match_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


Index(
    "ix_pvp_challenges_target_status",
    PvPChallengeRow.target_id,
    PvPChallengeRow.status,
    PvPChallengeRow.expires_at,
)
Index(
    "ix_pvp_challenges_challenger_status",
    PvPChallengeRow.challenger_id,
    PvPChallengeRow.status,
    PvPChallengeRow.expires_at,
)
Index(
    "ix_pvp_challenges_pair_status",
    PvPChallengeRow.challenger_id,
    PvPChallengeRow.target_id,
    PvPChallengeRow.status,
)
