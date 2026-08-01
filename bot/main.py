from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from redis.asyncio import from_url

from .config import Settings
from .database import Database
from .guard import RequestGuard
from .handlers import router as core_router
from .llm import JudgeEngine
from .privacy import PrivacyConfirmationStore
from .sql_profile_store import SQLProfileStore
from .storage import RedisStore
from .v03_engine import V03DebateEngine
from .v03_handlers import router as v03_router
from .v04_handlers import router as v04_router


async def set_commands(bot: Bot) -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Инструкция и список команд"),
            BotCommand(command="debate", description="Начать спор"),
            BotCommand(command="role", description="Изменить стиль оппонента"),
            BotCommand(command="difficulty", description="Выбрать сложность"),
            BotCommand(command="summary", description="Краткое резюме спора"),
            BotCommand(command="judge", description="Независимый судья"),
            BotCommand(command="fallacies", description="Найти логические ошибки"),
            BotCommand(command="tournament", description="Турнир из трёх раундов"),
            BotCommand(command="history", description="История сохранённых споров"),
            BotCommand(command="rematch", description="Повторить последнюю тему"),
            BotCommand(command="stats", description="Расширенная статистика"),
            BotCommand(command="achievements", description="Достижения"),
            BotCommand(command="leaderboard", description="Таблица лидеров"),
            BotCommand(command="export", description="Экспортировать спор в Markdown"),
            BotCommand(command="privacy", description="Какие данные сохраняются"),
            BotCommand(command="delete_me", description="Удалить мои данные"),
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
    database = Database(settings.database_url, echo=settings.database_echo)
    await database.ping()
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
    leaderboard = SQLProfileStore(database.sessions, store)
    privacy = PrivacyConfirmationStore(redis, prefix=settings.redis_prefix)
    engine = V03DebateEngine(
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
    dispatcher.include_router(v04_router)
    dispatcher.include_router(v03_router)
    dispatcher.include_router(core_router)
    await set_commands(bot)

    try:
        await dispatcher.start_polling(
            bot,
            store=store,
            leaderboard=leaderboard,
            engine=engine,
            judge_engine=judge_engine,
            guard=guard,
            privacy=privacy,
            settings=settings,
            allowed_updates=dispatcher.resolve_used_update_types(),
        )
    finally:
        await engine.close()
        await judge_engine.close()
        await store.close()
        await database.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
