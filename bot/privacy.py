from __future__ import annotations

import secrets
import time
from typing import Any


class PrivacyConfirmationStore:
    def __init__(
        self,
        redis: Any | None = None,
        *,
        prefix: str = "disputesbot",
        ttl_seconds: int = 300,
    ) -> None:
        self.redis = redis
        self.prefix = prefix
        self.ttl_seconds = ttl_seconds
        self._memory: dict[int, tuple[str, float]] = {}

    def _key(self, user_id: int) -> str:
        return f"{self.prefix}:delete-confirm:{user_id}"

    async def create(self, user_id: int) -> str:
        token = secrets.token_urlsafe(18)
        if self.redis is not None:
            await self.redis.set(self._key(user_id), token, ex=self.ttl_seconds)
        else:
            self._memory[user_id] = (token, time.monotonic() + self.ttl_seconds)
        return token

    async def consume(self, user_id: int, token: str) -> bool:
        if self.redis is not None:
            raw = await self.redis.getdel(self._key(user_id))
            if raw is None:
                return False
            stored = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
            return secrets.compare_digest(stored, token)
        value = self._memory.pop(user_id, None)
        if value is None:
            return False
        stored, expires_at = value
        return time.monotonic() <= expires_at and secrets.compare_digest(stored, token)

    async def cancel(self, user_id: int) -> None:
        if self.redis is not None:
            await self.redis.delete(self._key(user_id))
        self._memory.pop(user_id, None)

    async def delete_user_data(self, user_id: int) -> None:
        if self.redis is not None:
            await self.redis.delete(
                f"{self.prefix}:session:{user_id}",
                f"{self.prefix}:choices:{user_id}",
                f"{self.prefix}:role:{user_id}",
                f"{self.prefix}:difficulty:{user_id}",
                self._key(user_id),
            )
        self._memory.pop(user_id, None)
