from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand

from .config import Settings
from .handlers import router
from .llm import DebateEngine
from .storage import LeaderboardStore, MemoryStore


async def set_commands(bot: Bot) -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Инструкция и список команд"),
            BotCommand(command="debate", description="Начать спор на выбранную тему"),
            BotCommand(command="role", description="Изменить стиль оппонента"),
            BotCommand(command="summary", description="Краткое резюме спора"),
            BotCommand(command="judge", description="Выбрать победителя"),
            BotCommand(command="tournament", description="Турнир из трёх раундов"),
            BotCommand(command="leaderboard", description="Таблица лидеров"),
        ]
    )


async def main() -> None:
    settings = Settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        stream=sys.stdout,
    )

    bot = Bot(token=settings.bot_token.get_secret_value())
    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    store = MemoryStore()
    leaderboard = LeaderboardStore(settings.leaderboard_path)
    engine = DebateEngine(
        api_key=settings.openai_api_key.get_secret_value(),
        model=settings.openai_model,
        base_url=settings.openai_base_url,
    )

    await set_commands(bot)
    try:
        await dispatcher.start_polling(
            bot,
            store=store,
            leaderboard=leaderboard,
            engine=engine,
        )
    finally:
        await engine.close()


if __name__ == "__main__":
    asyncio.run(main())
