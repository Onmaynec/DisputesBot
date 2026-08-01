from __future__ import annotations

import asyncio
import logging

from aiogram import Bot

from .pvp_flow import notify_result
from .pvp_models import PvPStatus
from .pvp_repository import PvPRepository
from .pvp_store import PvPStore

logger = logging.getLogger(__name__)


async def sweep_expired_matches(
    bot: Bot,
    pvp_store: PvPStore,
    pvp_repository: PvPRepository,
) -> int:
    completed = 0
    for candidate in await pvp_store.list_active_matches():
        if candidate.status is not PvPStatus.ACTIVE or not candidate.is_expired():
            continue
        async with pvp_store.hold_match(candidate.match_id) as acquired:
            if not acquired:
                continue
            match = await pvp_store.get_match(candidate.match_id)
            if match is None or match.status is not PvPStatus.ACTIVE:
                continue
            if not match.is_expired():
                continue
            if not match.arguments:
                match.cancel()
                await pvp_store.finish_match(match)
                for user_id in (match.pro.user_id, match.con.user_id):
                    await bot.send_message(
                        user_id,
                        "⌛ PvP-дуэль отменена: первый ход не был сделан вовремя. "
                        "Elo не изменён.",
                    )
                completed += 1
                continue
            loser_id = match.current_user_id
            if loser_id is None:
                continue
            match.timeout(loser_id)
            result = await pvp_repository.record_match(match)
            await pvp_store.finish_match(match)
            await notify_result(bot, match, result)
            completed += 1
    return completed


async def run_timeout_sweeper(
    bot: Bot,
    pvp_store: PvPStore,
    pvp_repository: PvPRepository,
    *,
    interval_seconds: int,
) -> None:
    interval = max(5, interval_seconds)
    while True:
        try:
            await sweep_expired_matches(bot, pvp_store, pvp_repository)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("PvP timeout sweep failed")
        await asyncio.sleep(interval)
