from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .challenge_database import PvPChallengeRow
from .challenge_models import (
    ChallengeAccessError,
    ChallengeBlockedError,
    ChallengeInbox,
    ChallengeNotFoundError,
    ChallengeStatus,
    ChallengeUnavailableError,
    ChallengeUnknownTargetError,
    ChallengeUser,
    ChallengeView,
)
from .database import PvPBlockRow, UserProfileRow
from .pvp_models import PvPUser


class ChallengeRepository:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        *,
        ttl_hours: int = 24,
    ) -> None:
        if not 1 <= ttl_hours <= 168:
            raise ValueError("ttl_hours must be between 1 and 168")
        self.sessions = sessions
        self.ttl_hours = ttl_hours

    async def resolve_user(self, user_id: int) -> PvPUser | None:
        async with self.sessions() as db:
            profile = await db.get(UserProfileRow, user_id)
        if profile is None:
            return None
        return PvPUser(
            user_id=profile.user_id,
            username=profile.username,
            display_name=profile.display_name,
        )

    async def create(
        self,
        challenger: PvPUser,
        target: PvPUser,
        *,
        season: str,
        topic: str,
        now: datetime | None = None,
    ) -> tuple[bool, ChallengeView]:
        if challenger.user_id == target.user_id:
            raise ChallengeAccessError("Нельзя вызвать самого себя")
        normalized_topic = topic.strip()
        if not normalized_topic:
            raise ValueError("Challenge topic cannot be empty")
        reference = now or datetime.now(UTC)
        expires_at = reference + timedelta(hours=self.ttl_hours)
        async with self.sessions.begin() as db:
            await self._ensure_profile(db, challenger, reference)
            await self._ensure_profile(db, target, reference)
            if not await self._pair_allowed(db, challenger.user_id, target.user_id):
                raise ChallengeBlockedError("Вызов недоступен из-за блокировки")
            await self._refresh_states(db, reference)
            existing = await db.scalar(
                select(PvPChallengeRow)
                .where(
                    PvPChallengeRow.season == season,
                    PvPChallengeRow.status.in_(
                        [ChallengeStatus.PENDING.value, ChallengeStatus.ACCEPTING.value]
                    ),
                    PvPChallengeRow.expires_at > reference,
                    or_(
                        (
                            (PvPChallengeRow.challenger_id == challenger.user_id)
                            & (PvPChallengeRow.target_id == target.user_id)
                        ),
                        (
                            (PvPChallengeRow.challenger_id == target.user_id)
                            & (PvPChallengeRow.target_id == challenger.user_id)
                        ),
                    ),
                )
                .order_by(PvPChallengeRow.created_at.asc())
                .limit(1)
            )
            if existing is not None:
                return False, await self._view(db, existing)
            row = PvPChallengeRow(
                challenge_id=uuid4().hex[:12],
                challenger_id=challenger.user_id,
                target_id=target.user_id,
                season=season,
                topic=normalized_topic,
                status=ChallengeStatus.PENDING.value,
                created_at=reference,
                expires_at=expires_at,
            )
            db.add(row)
            await db.flush()
            return True, await self._view(db, row)

    async def inbox(
        self,
        user_id: int,
        season: str,
        *,
        now: datetime | None = None,
    ) -> ChallengeInbox:
        reference = now or datetime.now(UTC)
        async with self.sessions.begin() as db:
            await self._refresh_states(db, reference)
            rows = (
                await db.scalars(
                    select(PvPChallengeRow)
                    .where(
                        PvPChallengeRow.season == season,
                        PvPChallengeRow.status.in_(
                            [ChallengeStatus.PENDING.value, ChallengeStatus.ACCEPTING.value]
                        ),
                        or_(
                            PvPChallengeRow.challenger_id == user_id,
                            PvPChallengeRow.target_id == user_id,
                        ),
                    )
                    .order_by(PvPChallengeRow.created_at.desc())
                )
            ).all()
            views = [await self._view(db, row) for row in rows]
        return ChallengeInbox(
            incoming=tuple(item for item in views if item.target.user_id == user_id),
            outgoing=tuple(item for item in views if item.challenger.user_id == user_id),
        )

    async def claim_accept(
        self,
        challenge_id: str,
        target_id: int,
        *,
        now: datetime | None = None,
    ) -> ChallengeView:
        reference = now or datetime.now(UTC)
        async with self.sessions.begin() as db:
            await self._refresh_states(db, reference)
            row = await db.get(PvPChallengeRow, challenge_id, with_for_update=True)
            if row is None:
                raise ChallengeNotFoundError("Вызов не найден")
            if row.target_id != target_id:
                raise ChallengeAccessError("Принять вызов может только приглашённый игрок")
            if row.status != ChallengeStatus.PENDING.value:
                raise ChallengeUnavailableError("Вызов уже обработан или занят")
            if self._as_utc(row.expires_at) <= reference:
                row.status = ChallengeStatus.EXPIRED.value
                row.resolved_at = reference
                raise ChallengeUnavailableError("Срок действия вызова истёк")
            if not await self._pair_allowed(db, row.challenger_id, row.target_id):
                row.status = ChallengeStatus.CANCELLED.value
                row.resolved_at = reference
                raise ChallengeBlockedError("Вызов недоступен из-за блокировки")
            row.status = ChallengeStatus.ACCEPTING.value
            row.resolved_at = reference
            await db.flush()
            return await self._view(db, row)

    async def complete_accept(
        self,
        challenge_id: str,
        match_id: str,
        *,
        now: datetime | None = None,
    ) -> None:
        reference = now or datetime.now(UTC)
        async with self.sessions.begin() as db:
            row = await db.get(PvPChallengeRow, challenge_id, with_for_update=True)
            if row is None:
                raise ChallengeNotFoundError("Вызов не найден")
            if row.status != ChallengeStatus.ACCEPTING.value:
                raise ChallengeUnavailableError("Вызов не зарезервирован для принятия")
            row.status = ChallengeStatus.ACCEPTED.value
            row.match_id = match_id
            row.resolved_at = reference

    async def release_accept(
        self,
        challenge_id: str,
        *,
        now: datetime | None = None,
    ) -> None:
        reference = now or datetime.now(UTC)
        async with self.sessions.begin() as db:
            row = await db.get(PvPChallengeRow, challenge_id, with_for_update=True)
            if row is None or row.status != ChallengeStatus.ACCEPTING.value:
                return
            if self._as_utc(row.expires_at) <= reference:
                row.status = ChallengeStatus.EXPIRED.value
                row.resolved_at = reference
            else:
                row.status = ChallengeStatus.PENDING.value
                row.resolved_at = None

    async def decline(
        self,
        challenge_id: str,
        target_id: int,
        *,
        now: datetime | None = None,
    ) -> ChallengeView:
        return await self._resolve(
            challenge_id,
            actor_id=target_id,
            actor_field="target",
            status=ChallengeStatus.DECLINED,
            now=now,
        )

    async def cancel(
        self,
        challenge_id: str,
        challenger_id: int,
        *,
        now: datetime | None = None,
    ) -> ChallengeView:
        return await self._resolve(
            challenge_id,
            actor_id=challenger_id,
            actor_field="challenger",
            status=ChallengeStatus.CANCELLED,
            now=now,
        )

    async def delete_user_data(self, user_id: int) -> None:
        async with self.sessions.begin() as db:
            await db.execute(
                delete(PvPChallengeRow).where(
                    or_(
                        PvPChallengeRow.challenger_id == user_id,
                        PvPChallengeRow.target_id == user_id,
                    )
                )
            )

    async def _resolve(
        self,
        challenge_id: str,
        *,
        actor_id: int,
        actor_field: str,
        status: ChallengeStatus,
        now: datetime | None,
    ) -> ChallengeView:
        reference = now or datetime.now(UTC)
        async with self.sessions.begin() as db:
            await self._refresh_states(db, reference)
            row = await db.get(PvPChallengeRow, challenge_id, with_for_update=True)
            if row is None:
                raise ChallengeNotFoundError("Вызов не найден")
            expected_id = row.target_id if actor_field == "target" else row.challenger_id
            if expected_id != actor_id:
                raise ChallengeAccessError("Недостаточно прав для этого вызова")
            if row.status != ChallengeStatus.PENDING.value:
                raise ChallengeUnavailableError("Вызов уже обработан")
            row.status = status.value
            row.resolved_at = reference
            await db.flush()
            return await self._view(db, row)

    @staticmethod
    async def _ensure_profile(
        db: AsyncSession,
        user: PvPUser,
        reference: datetime,
    ) -> UserProfileRow:
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
        return profile

    @staticmethod
    async def _pair_allowed(db: AsyncSession, first_id: int, second_id: int) -> bool:
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

    @staticmethod
    async def _refresh_states(db: AsyncSession, reference: datetime) -> None:
        stale_accepting = reference - timedelta(minutes=5)
        await db.execute(
            update(PvPChallengeRow)
            .where(
                PvPChallengeRow.status == ChallengeStatus.ACCEPTING.value,
                PvPChallengeRow.resolved_at <= stale_accepting,
                PvPChallengeRow.expires_at > reference,
            )
            .values(status=ChallengeStatus.PENDING.value, resolved_at=None)
        )
        await db.execute(
            update(PvPChallengeRow)
            .where(
                PvPChallengeRow.status.in_(
                    [ChallengeStatus.PENDING.value, ChallengeStatus.ACCEPTING.value]
                ),
                PvPChallengeRow.expires_at <= reference,
            )
            .values(status=ChallengeStatus.EXPIRED.value, resolved_at=reference)
        )

    @staticmethod
    async def _view(db: AsyncSession, row: PvPChallengeRow) -> ChallengeView:
        challenger = await db.get(UserProfileRow, row.challenger_id)
        target = await db.get(UserProfileRow, row.target_id)
        if challenger is None or target is None:
            raise ChallengeUnknownTargetError("Профиль участника вызова не найден")
        return ChallengeView(
            challenge_id=row.challenge_id,
            challenger=ChallengeUser(
                user_id=challenger.user_id,
                display_name=challenger.display_name,
                username=challenger.username,
            ),
            target=ChallengeUser(
                user_id=target.user_id,
                display_name=target.display_name,
                username=target.username,
            ),
            season=row.season,
            topic=row.topic,
            status=ChallengeStatus(row.status),
            created_at=ChallengeRepository._as_utc(row.created_at),
            expires_at=ChallengeRepository._as_utc(row.expires_at),
            resolved_at=(
                ChallengeRepository._as_utc(row.resolved_at)
                if row.resolved_at is not None
                else None
            ),
            match_id=row.match_id,
        )

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
