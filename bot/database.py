from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class UserProfileRow(Base):
    __tablename__ = "user_profiles"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    display_name: Mapped[str] = mapped_column(String(255), default="Пользователь")
    tournaments: Mapped[int] = mapped_column(Integer, default=0)
    regular_debates: Mapped[int] = mapped_column(Integer, default=0)
    completed_debates: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    draws: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)
    best_total: Mapped[int] = mapped_column(Integer, default=0)
    average_total: Mapped[float] = mapped_column(Float, default=0.0)
    last_scores: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    score_totals: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    xp: Mapped[int] = mapped_column(Integer, default=0)
    level: Mapped[int] = mapped_column(Integer, default=1)
    current_streak: Mapped[int] = mapped_column(Integer, default=0)
    best_streak: Mapped[int] = mapped_column(Integer, default=0)
    fallacy_analyses: Mapped[int] = mapped_column(Integer, default=0)
    fallacy_counts: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    achievements: Mapped[list[str]] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    archives: Mapped[list[DebateArchiveRow]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class DebateArchiveRow(Base):
    __tablename__ = "debate_archives"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("user_profiles.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    topic: Mapped[str] = mapped_column(Text)
    mode: Mapped[str] = mapped_column(String(24))
    role: Mapped[str] = mapped_column(String(64))
    difficulty: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(24))
    winner: Mapped[str] = mapped_column(String(16), default="none")
    score_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    user_argument_count: Mapped[int] = mapped_column(Integer, default=0)
    user_stance: Mapped[str | None] = mapped_column(String(16), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fallacies: Mapped[list[str]] = mapped_column(JSON, default=list)
    transcript: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)

    profile: Mapped[UserProfileRow] = relationship(back_populates="archives")


class PvPPlayerRow(Base):
    __tablename__ = "pvp_players"

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("user_profiles.user_id", ondelete="CASCADE"),
        primary_key=True,
        autoincrement=False,
    )
    season: Mapped[str] = mapped_column(String(32), primary_key=True)
    rating: Mapped[int] = mapped_column(Integer, default=1000)
    games: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    draws: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class PvPMatchRow(Base):
    __tablename__ = "pvp_matches"

    match_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    season: Mapped[str] = mapped_column(String(32), nullable=False)
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    pair_key: Mapped[str | None] = mapped_column(String(48), nullable=True)
    pro_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("user_profiles.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    con_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("user_profiles.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    winner_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    rated: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    unrated_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pro_rating_before: Mapped[int] = mapped_column(Integer, nullable=False)
    pro_rating_after: Mapped[int] = mapped_column(Integer, nullable=False)
    con_rating_before: Mapped[int] = mapped_column(Integer, nullable=False)
    con_rating_after: Mapped[int] = mapped_column(Integer, nullable=False)
    pro_scores: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    con_scores: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    transcript: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PvPBlockRow(Base):
    __tablename__ = "pvp_blocks"

    blocker_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("user_profiles.user_id", ondelete="CASCADE"),
        primary_key=True,
        autoincrement=False,
    )
    blocked_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=False,
    )
    blocked_label: Mapped[str] = mapped_column(String(255), default="Пользователь")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )


class PvPReportRow(Base):
    __tablename__ = "pvp_reports"

    report_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    match_id: Mapped[str] = mapped_column(String(64), nullable=False)
    match_topic: Mapped[str] = mapped_column(Text, nullable=False)
    reporter_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    opponent_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    category: Mapped[str] = mapped_column(String(24), nullable=False)
    comment: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(16), default="open", nullable=False)
    moderator_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    moderation_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


Index("ix_debate_archives_user_ended", DebateArchiveRow.user_id, DebateArchiveRow.ended_at)
Index("ix_user_profiles_ranking", UserProfileRow.best_total, UserProfileRow.average_total)
Index("ix_pvp_players_season_rating", PvPPlayerRow.season, PvPPlayerRow.rating)
Index("ix_pvp_matches_pro_ended", PvPMatchRow.pro_user_id, PvPMatchRow.ended_at)
Index("ix_pvp_matches_con_ended", PvPMatchRow.con_user_id, PvPMatchRow.ended_at)
Index("ix_pvp_matches_pair_ended", PvPMatchRow.pair_key, PvPMatchRow.ended_at)
Index("ix_pvp_blocks_blocked", PvPBlockRow.blocked_id)
Index("ix_pvp_reports_status_created", PvPReportRow.status, PvPReportRow.created_at)
Index("ix_pvp_reports_reporter_created", PvPReportRow.reporter_id, PvPReportRow.created_at)


class Database:
    def __init__(self, url: str, *, echo: bool = False) -> None:
        self.engine: AsyncEngine = create_async_engine(url, echo=echo, pool_pre_ping=True)
        self.sessions = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def ping(self) -> None:
        async with self.engine.connect() as connection:
            await connection.exec_driver_sql("SELECT 1")

    async def create_all_for_tests(self) -> None:
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def close(self) -> None:
        await self.engine.dispose()
