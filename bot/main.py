from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from redis.asyncio import from_url

from .config import Settings
from .guard import RequestGuard
from .handlers import router
from .llm import DebateEngine, JudgeEngine
from .storage import LeaderboardStore, RedisStore


async def set_commands(bot: Bot) -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Инструкция и список команд"),
            BotCommand(command="debate", description="Начать спор на выбранную тему"),
            BotCommand(command="role", description="Изменить стиль оппонента"),
            BotCommand(command="difficulty", description="Выбрать сложность"),
            BotCommand(command="summary", description="Краткое резюме спора"),
            BotCommand(command="judge", description="Независимый судья"),
            BotCommand(command="tournament", description="Турнир из трёх раундов"),
            BotCommand(command="leaderboard", description="Таблица лидеров"),
            BotCommand(command="stats", description="Личная статистика"),
            BotCommand(command="cancel", description="Завершить активный спор"),
        ]
    )


async def main() -> None:
    settings = Settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        stream=sys.stdout,
    )

    redis = from_url(settings.redis_url)
    await redis.ping()
    store = RedisStore(
        redis,
        session_ttl_seconds=settings.session_ttl_seconds,
        prefix=settings.redis_prefix,
    )
    guard = RequestGuard(
        redis=redis,
        requests=settings.rate_limit_requests,
        window_seconds=settings.rate_limit_window_seconds,
        lock_ttl_seconds=settings.request_lock_ttl_seconds,
        prefix=settings.redis_prefix,
    )
    leaderboard = LeaderboardStore(settings.leaderboard_path)
    engine = DebateEngine(
        api_key=settings.openai_api_key.get_secret_value(),
        model=settings.openai_model,
        base_url=settings.openai_base_url,
    )
    judge_engine = JudgeEngine(
        api_key=settings.openai_api_key.get_secret_value(),
        model=settings.openai_judge_model or settings.openai_model,
        base_url=settings.openai_base_url,
    )

    bot = Bot(token=settings.bot_token.get_secret_value())
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    await set_commands(bot)

    try:
        await dispatcher.start_polling(
            bot,
            store=store,
            leaderboard=leaderboard,
            engine=engine,
            judge_engine=judge_engine,
            guard=guard,
            settings=settings,
            allowed_updates=dispatcher.resolve_used_update_types(),
        )
    finally:
        await engine.close()
        await judge_engine.close()
        await store.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
