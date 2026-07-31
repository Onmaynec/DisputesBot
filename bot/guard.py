from __future__ import annotations

import asyncio
import secrets
import time
from collections import defaultdict, deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any


class RequestGuard:
    """Per-user non-blocking lock plus Redis-backed fixed-window rate limiting."""

    def __init__(
        self,
        *,
        redis: Any | None = None,
        requests: int = 5,
        window_seconds: int = 20,
        lock_ttl_seconds: int = 90,
        prefix: str = "disputesbot",
    ) -> None:
        self.redis = redis
        self.requests = requests
        self.window_seconds = window_seconds
        self.lock_ttl_seconds = lock_ttl_seconds
        self.prefix = prefix
        self._locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._events: defaultdict[int, deque[float]] = defaultdict(deque)

    async def retry_after(self, user_id: int) -> int:
        """Register a request and return 0 when allowed, otherwise seconds to retry."""

        if self.redis is not None:
            key = f"{self.prefix}:rate:{user_id}"
            count = await self.redis.incr(key)
            if count == 1:
                await self.redis.expire(key, self.window_seconds)
            if count <= self.requests:
                return 0
            ttl = await self.redis.ttl(key)
            return max(1, int(ttl) if ttl and ttl > 0 else self.window_seconds)

        now = time.monotonic()
        events = self._events[user_id]
        cutoff = now - self.window_seconds
        while events and events[0] <= cutoff:
            events.popleft()
        if len(events) >= self.requests:
            return max(1, int(self.window_seconds - (now - events[0])))
        events.append(now)
        return 0

    @asynccontextmanager
    async def hold(self, user_id: int) -> AsyncIterator[bool]:
        """Acquire local and distributed locks without queueing duplicate requests."""

        local_lock = self._locks[user_id]
        try:
            await asyncio.wait_for(local_lock.acquire(), timeout=0.01)
        except TimeoutError:
            yield False
            return

        redis_key = f"{self.prefix}:lock:{user_id}"
        token = secrets.token_hex(16)
        redis_acquired = False
        try:
            if self.redis is not None:
                redis_acquired = bool(
                    await self.redis.set(
                        redis_key,
                        token,
                        nx=True,
                        ex=self.lock_ttl_seconds,
                    )
                )
                if not redis_acquired:
                    yield False
                    return
            yield True
        finally:
            if self.redis is not None and redis_acquired:
                await self._release_redis_lock(redis_key, token)
            local_lock.release()

    async def _release_redis_lock(self, key: str, token: str) -> None:
        script = """
        if redis.call('get', KEYS[1]) == ARGV[1] then
            return redis.call('del', KEYS[1])
        end
        return 0
        """
        await self.redis.eval(script, 1, key, token)
