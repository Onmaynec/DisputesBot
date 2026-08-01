import pytest

from bot.privacy import PrivacyConfirmationStore


@pytest.mark.asyncio
async def test_confirmation_token_is_single_use() -> None:
    store = PrivacyConfirmationStore(ttl_seconds=60)
    token = await store.create(42)

    assert await store.consume(42, token)
    assert not await store.consume(42, token)


@pytest.mark.asyncio
async def test_wrong_token_consumes_confirmation_safely() -> None:
    store = PrivacyConfirmationStore(ttl_seconds=60)
    token = await store.create(42)

    assert not await store.consume(42, token + "wrong")
    assert not await store.consume(42, token)
