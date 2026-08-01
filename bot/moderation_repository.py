from __future__ import annotations

from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .database import PvPBlockRow, PvPMatchRow, PvPReportRow, UserProfileRow
from .moderation_models import (
    BlockedUserView,
    PvPReportView,
    ReportCategory,
    ReportStatus,
)
from .pvp_models import PvPMatch, PvPUser


class ModerationRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def block_user(
        self,
        blocker: PvPUser,
        blocked_id: int,
        *,
        blocked_label: str,
    ) -> bool:
        if blocker.user_id == blocked_id:
            raise ValueError("Нельзя заблокировать самого себя")
        async with self.sessions.begin() as db:
            await self._ensure_profile(db, blocker)
            key = {"blocker_id": blocker.user_id, "blocked_id": blocked_id}
            row = await db.get(PvPBlockRow, key, with_for_update=True)
            if row is not None:
                row.blocked_label = blocked_label[:255] or "Пользователь"
                return False
            db.add(
                PvPBlockRow(
                    blocker_id=blocker.user_id,
                    blocked_id=blocked_id,
                    blocked_label=blocked_label[:255] or "Пользователь",
                )
            )
        return True

    async def unblock_user(self, blocker_id: int, blocked_id: int) -> bool:
        async with self.sessions.begin() as db:
            result = await db.execute(
                delete(PvPBlockRow).where(
                    PvPBlockRow.blocker_id == blocker_id,
                    PvPBlockRow.blocked_id == blocked_id,
                )
            )
        return bool(result.rowcount)

    async def list_blocks(self, blocker_id: int) -> list[BlockedUserView]:
        async with self.sessions() as db:
            rows = (
                await db.scalars(
                    select(PvPBlockRow)
                    .where(PvPBlockRow.blocker_id == blocker_id)
                    .order_by(PvPBlockRow.created_at.desc())
                )
            ).all()
        return [
            BlockedUserView(
                user_id=row.blocked_id,
                label=row.blocked_label,
                created_at=row.created_at,
            )
            for row in rows
        ]

    async def pair_allowed(self, first_id: int, second_id: int) -> bool:
        if first_id == second_id:
            return False
        async with self.sessions() as db:
            blocked = await db.scalar(
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
        return blocked is None

    async def create_report(
        self,
        *,
        reporter_id: int,
        category: ReportCategory,
        comment: str,
        match: PvPMatch | None = None,
        match_id: str | None = None,
    ) -> tuple[bool, PvPReportView]:
        normalized = comment.strip()
        if len(normalized) > 500:
            raise ValueError("Комментарий длиннее 500 символов")
        async with self.sessions.begin() as db:
            stored: PvPMatchRow | None = None
            if match is None:
                if not match_id:
                    raise ValueError("Матч не указан")
                stored = await db.get(PvPMatchRow, match_id)
                if stored is None:
                    raise ValueError("Матч не найден")
                participants = {stored.pro_user_id, stored.con_user_id}
                topic = stored.topic
                resolved_match_id = stored.match_id
                opponent_id = (
                    stored.con_user_id
                    if reporter_id == stored.pro_user_id
                    else stored.pro_user_id
                )
            else:
                participants = {match.pro.user_id, match.con.user_id}
                topic = match.topic
                resolved_match_id = match.match_id
                opponent_id = match.opponent(reporter_id).user_id
            if reporter_id not in participants:
                raise ValueError("Жалобу может создать только участник матча")

            report_id = uuid5(
                NAMESPACE_URL,
                f"disputesbot:{resolved_match_id}:{reporter_id}",
            ).hex
            existing = await db.get(PvPReportRow, report_id, with_for_update=True)
            if existing is not None:
                return False, self._report_view(existing)
            row = PvPReportRow(
                report_id=report_id,
                match_id=resolved_match_id,
                match_topic=topic,
                reporter_id=reporter_id,
                opponent_user_id=opponent_id,
                category=category.value,
                comment=normalized,
            )
            db.add(row)
            await db.flush()
            return True, self._report_view(row)

    async def my_reports(self, reporter_id: int, limit: int = 10) -> list[PvPReportView]:
        async with self.sessions() as db:
            rows = (
                await db.scalars(
                    select(PvPReportRow)
                    .where(PvPReportRow.reporter_id == reporter_id)
                    .order_by(PvPReportRow.created_at.desc())
                    .limit(max(1, min(limit, 20)))
                )
            ).all()
        return [self._report_view(row) for row in rows]

    async def list_reports(
        self,
        status: ReportStatus = ReportStatus.OPEN,
        *,
        limit: int = 20,
    ) -> list[PvPReportView]:
        async with self.sessions() as db:
            rows = (
                await db.scalars(
                    select(PvPReportRow)
                    .where(PvPReportRow.status == status.value)
                    .order_by(PvPReportRow.created_at.asc())
                    .limit(max(1, min(limit, 50)))
                )
            ).all()
        return [self._report_view(row) for row in rows]

    async def resolve_report(
        self,
        report_id: str,
        *,
        status: ReportStatus,
        moderator_id: int,
        note: str = "",
    ) -> tuple[bool, PvPReportView | None]:
        if status is ReportStatus.OPEN:
            raise ValueError("Нельзя вернуть жалобу в open этой командой")
        normalized = note.strip()
        if len(normalized) > 500:
            raise ValueError("Заметка длиннее 500 символов")
        async with self.sessions.begin() as db:
            row = await db.get(PvPReportRow, report_id, with_for_update=True)
            if row is None:
                return False, None
            if row.status == status.value:
                return False, self._report_view(row)
            if row.status != ReportStatus.OPEN.value:
                return False, self._report_view(row)
            row.status = status.value
            row.moderator_id = moderator_id
            row.moderation_note = normalized or None
            row.resolved_at = datetime.now(UTC)
            await db.flush()
            return True, self._report_view(row)

    async def open_report_count(self) -> int:
        async with self.sessions() as db:
            rows = await db.scalars(
                select(PvPReportRow.report_id).where(
                    PvPReportRow.status == ReportStatus.OPEN.value
                )
            )
            return len(rows.all())

    async def anonymize_user(self, user_id: int) -> None:
        async with self.sessions.begin() as db:
            await db.execute(
                delete(PvPBlockRow).where(
                    or_(
                        PvPBlockRow.blocker_id == user_id,
                        PvPBlockRow.blocked_id == user_id,
                    )
                )
            )
            await db.execute(
                update(PvPReportRow)
                .where(PvPReportRow.reporter_id == user_id)
                .values(reporter_id=None)
            )

    @staticmethod
    async def _ensure_profile(db: AsyncSession, user: PvPUser) -> UserProfileRow:
        row = await db.get(UserProfileRow, user.user_id, with_for_update=True)
        if row is None:
            row = UserProfileRow(
                user_id=user.user_id,
                username=user.username,
                display_name=user.display_name,
            )
            db.add(row)
            await db.flush()
        else:
            row.username = user.username
            row.display_name = user.display_name
            row.updated_at = datetime.now(UTC)
        return row

    @staticmethod
    def _report_view(row: PvPReportRow) -> PvPReportView:
        return PvPReportView(
            report_id=row.report_id,
            match_id=row.match_id,
            match_topic=row.match_topic,
            reporter_id=row.reporter_id,
            opponent_user_id=row.opponent_user_id,
            category=ReportCategory(row.category),
            comment=row.comment,
            status=ReportStatus(row.status),
            moderator_id=row.moderator_id,
            moderation_note=row.moderation_note,
            created_at=row.created_at,
            resolved_at=row.resolved_at,
        )
