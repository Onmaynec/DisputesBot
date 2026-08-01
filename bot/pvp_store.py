from __future__ import annotations

import asyncio
import json
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

from .models import Stance
from .pvp_models import (
    PvPInvitation,
    PvPMatch,
    PvPParticipant,
    PvPQueueEntry,
    PvPUser,
)


class PvPBusyError(RuntimeError):
    pass


class PvPStore:
    def __init__(
        self,
        redis: Any,
        *,
        prefix: str = "disputesbot",
        match_ttl_seconds: int = 86_400,
        invitation_ttl_seconds: int = 600,
        queue_ttl_seconds: int = 1_800,
        lock_ttl_seconds: int = 15,
    ) -> None:
        self.redis = redis
        self.prefix = prefix
        self.match_ttl_seconds = match_ttl_seconds
        self.invitation_ttl_seconds = invitation_ttl_seconds
        self.queue_ttl_seconds = queue_ttl_seconds
        self.lock_ttl_seconds = lock_ttl_seconds

    def _key(self, kind: str, value: str | int | None = None) -> str:
        base = f"{self.prefix}:pvp:{kind}"
        return f"{base}:{value}" if value is not None else base

    @asynccontextmanager
    async def hold_match(self, match_id: str) -> AsyncIterator[bool]:
        async with self._named_lock(f"match:{match_id}") as acquired:
            yield acquired

    async def get_match(self, match_id: str) -> PvPMatch | None:
        raw = await self.redis.get(self._key("match", match_id))
        if raw is None:
            return None
        try:
            return PvPMatch.model_validate_json(self._decode(raw))
        except ValueError:
            await self.redis.delete(self._key("match", match_id))
            return None

    async def get_match_for_user(self, user_id: int) -> PvPMatch | None:
        index_key = self._key("user", user_id)
        raw_match_id = await self.redis.get(index_key)
        if raw_match_id is None:
            return None
        match_id = self._decode(raw_match_id)
        match = await self.get_match(match_id)
        if match is None:
            await self.redis.delete(index_key)
            return None
        try:
            match.participant(user_id)
        except ValueError:
            await self.redis.delete(index_key)
            return None
        return match

    async def save_match(self, match: PvPMatch) -> None:
        match.updated_at = datetime.now(UTC)
        payload = match.model_dump_json()
        await self.redis.set(
            self._key("match", match.match_id),
            payload,
            ex=self.match_ttl_seconds,
        )
        for user_id in (match.pro.user_id, match.con.user_id):
            await self.redis.set(
                self._key("user", user_id),
                match.match_id,
                ex=self.match_ttl_seconds,
            )

    async def create_match(
        self,
        first: PvPUser,
        second: PvPUser,
        *,
        topic: str,
        season: str,
        first_is_pro: bool | None = None,
    ) -> PvPMatch:
        if first.user_id == second.user_id:
            raise ValueError("Cannot create a PvP match with the same user")
        if first_is_pro is None:
            first_is_pro = secrets.randbelow(2) == 0
        pro_user, con_user = (first, second) if first_is_pro else (second, first)
        user_ids = (first.user_id, second.user_id)
        async with self._user_locks(user_ids) as acquired:
            if not acquired:
                raise PvPBusyError("Participant is being matched by another request")
            active = await self.redis.mget(
                self._key("user", user_ids[0]),
                self._key("user", user_ids[1]),
            )
            if any(item is not None for item in active):
                raise PvPBusyError("One of the participants already has an active match")
            match = PvPMatch(
                topic=topic,
                season=season,
                pro=PvPParticipant(**pro_user.model_dump(), stance=Stance.PRO),
                con=PvPParticipant(**con_user.model_dump(), stance=Stance.CON),
            )
            await self.save_match(match)
            return match

    async def finish_match(self, match: PvPMatch) -> None:
        await self._delete_match_state(match)

    async def cancel_match(self, match: PvPMatch) -> None:
        match.cancel()
        await self._delete_match_state(match)

    async def _delete_match_state(self, match: PvPMatch) -> None:
        keys = [self._key("match", match.match_id)]
        for user_id in (match.pro.user_id, match.con.user_id):
            index_key = self._key("user", user_id)
            raw = await self.redis.get(index_key)
            if raw is not None and self._decode(raw) == match.match_id:
                keys.append(index_key)
        await self.redis.delete(*keys)

    async def create_invitation(
        self,
        inviter: PvPUser,
        *,
        topic: str,
        season: str,
    ) -> PvPInvitation:
        previous = await self.redis.get(self._key("invite-user", inviter.user_id))
        if previous is not None:
            await self.redis.delete(self._key("invite", self._decode(previous)))
        invitation = PvPInvitation(inviter=inviter, topic=topic, season=season)
        await self.redis.set(
            self._key("invite", invitation.token),
            invitation.model_dump_json(),
            ex=self.invitation_ttl_seconds,
        )
        await self.redis.set(
            self._key("invite-user", inviter.user_id),
            invitation.token,
            ex=self.invitation_ttl_seconds,
        )
        return invitation

    async def get_invitation(self, token: str) -> PvPInvitation | None:
        raw = await self.redis.get(self._key("invite", token))
        if raw is None:
            return None
        try:
            return PvPInvitation.model_validate_json(self._decode(raw))
        except ValueError:
            await self.redis.delete(self._key("invite", token))
            return None

    async def consume_invitation(self, token: str) -> PvPInvitation | None:
        raw = await self.redis.getdel(self._key("invite", token))
        if raw is None:
            return None
        try:
            invitation = PvPInvitation.model_validate_json(self._decode(raw))
        except ValueError:
            return None
        index_key = self._key("invite-user", invitation.inviter.user_id)
        indexed = await self.redis.get(index_key)
        if indexed is not None and self._decode(indexed) == token:
            await self.redis.delete(index_key)
        return invitation

    async def cancel_invitation(self, token: str, user_id: int) -> bool:
        raw = await self.redis.get(self._key("invite", token))
        if raw is None:
            return False
        try:
            invitation = PvPInvitation.model_validate_json(self._decode(raw))
        except ValueError:
            await self.redis.delete(self._key("invite", token))
            return False
        if invitation.inviter.user_id != user_id:
            return False
        await self.redis.delete(
            self._key("invite", token),
            self._key("invite-user", user_id),
        )
        return True

    async def join_queue(self, entry: PvPQueueEntry) -> PvPMatch | None:
        async with self._named_lock("queue") as acquired:
            if not acquired:
                raise PvPBusyError("Matchmaking queue is busy")
            if await self.get_match_for_user(entry.participant.user_id) is not None:
                raise PvPBusyError("User already has an active match")
            queue = await self._load_queue()
            now = datetime.now(UTC)
            minimum_time = now - timedelta(seconds=self.queue_ttl_seconds)
            filtered: list[PvPQueueEntry] = []
            for item in queue:
                if item.queued_at < minimum_time:
                    continue
                if item.participant.user_id == entry.participant.user_id:
                    continue
                if item.season != entry.season:
                    continue
                if await self.get_match_for_user(item.participant.user_id) is not None:
                    continue
                filtered.append(item)

            if filtered:
                opponent = filtered.pop(0)
                await self._save_queue(filtered)
                try:
                    return await self.create_match(
                        opponent.participant,
                        entry.participant,
                        topic=opponent.topic,
                        season=entry.season,
                    )
                except PvPBusyError:
                    filtered.append(opponent)
                    filtered.append(entry)
                    await self._save_queue(filtered)
                    raise

            filtered.append(entry)
            await self._save_queue(filtered)
            return None

    async def leave_queue(self, user_id: int) -> bool:
        async with self._named_lock("queue") as acquired:
            if not acquired:
                raise PvPBusyError("Matchmaking queue is busy")
            queue = await self._load_queue()
            remaining = [item for item in queue if item.participant.user_id != user_id]
            changed = len(remaining) != len(queue)
            if changed:
                await self._save_queue(remaining)
            return changed

    async def delete_user_data(self, user_id: int) -> None:
        for _ in range(3):
            try:
                await self.leave_queue(user_id)
                break
            except PvPBusyError:
                await asyncio.sleep(0)
        invite_token = await self.redis.get(self._key("invite-user", user_id))
        if invite_token is not None:
            await self.redis.delete(
                self._key("invite", self._decode(invite_token)),
                self._key("invite-user", user_id),
            )
        match = await self.get_match_for_user(user_id)
        if match is not None:
            await self._delete_match_state(match)
        await self.redis.delete(self._key("user", user_id))

    async def _load_queue(self) -> list[PvPQueueEntry]:
        raw = await self.redis.get(self._key("queue"))
        if raw is None:
            return []
        try:
            payload = json.loads(self._decode(raw))
            return [PvPQueueEntry.model_validate(item) for item in payload]
        except (json.JSONDecodeError, ValueError, TypeError):
            await self.redis.delete(self._key("queue"))
            return []

    async def _save_queue(self, queue: list[PvPQueueEntry]) -> None:
        payload = json.dumps(
            [item.model_dump(mode="json") for item in queue],
            ensure_ascii=False,
        )
        await self.redis.set(self._key("queue"), payload)

    @asynccontextmanager
    async def _user_locks(self, user_ids: tuple[int, int]) -> AsyncIterator[bool]:
        acquired: list[tuple[str, str]] = []
        try:
            for user_id in sorted(user_ids):
                key = self._key("lock-user", user_id)
                token = secrets.token_hex(12)
                ok = await self.redis.set(
                    key,
                    token,
                    nx=True,
                    ex=self.lock_ttl_seconds,
                )
                if not ok:
                    yield False
                    return
                acquired.append((key, token))
            yield True
        finally:
            for key, token in reversed(acquired):
                await self._release_lock(key, token)

    @asynccontextmanager
    async def _named_lock(self, name: str) -> AsyncIterator[bool]:
        key = self._key("lock", name)
        token = secrets.token_hex(12)
        acquired = await self.redis.set(
            key,
            token,
            nx=True,
            ex=self.lock_ttl_seconds,
        )
        try:
            yield bool(acquired)
        finally:
            if acquired:
                await self._release_lock(key, token)

    async def _release_lock(self, key: str, token: str) -> None:
        raw = await self.redis.get(key)
        if raw is not None and secrets.compare_digest(self._decode(raw), token):
            await self.redis.delete(key)

    @staticmethod
    def _decode(value: Any) -> str:
        return value.decode("utf-8") if isinstance(value, bytes) else str(value)
