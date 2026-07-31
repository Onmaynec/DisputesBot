import asyncio

import pytest

from bot.guard import RequestGuard


@pytest.mark.asyncio
async def test_memory_rate_limit_returns_retry_after() -> None:
    guard = RequestGuard(requests=2, window_seconds=30)

    assert await guard.retry_after(1) == 0
    assert await guard.retry_after(1) == 0
    assert await guard.retry_after(1) > 0


@pytest.mark.asyncio
async def test_per_user_lock_rejects_parallel_request() -> None:
    guard = RequestGuard()
    entered = asyncio.Event()
    release = asyncio.Event()

    async def first() -> bool:
        async with guard.hold(42) as acquired:
            assert acquired
            entered.set()
            await release.wait()
            return acquired

    task = asyncio.create_task(first())
    await entered.wait()

    async with guard.hold(42) as acquired:
        assert not acquired

    release.set()
    assert await task
