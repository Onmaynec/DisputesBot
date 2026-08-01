from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class PvPProfileSettingRow(Base):
    __tablename__ = "pvp_profile_settings"

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("user_profiles.user_id", ondelete="CASCADE"),
        primary_key=True,
        autoincrement=False,
    )
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


Index("ix_pvp_profile_settings_public", PvPProfileSettingRow.is_public)
