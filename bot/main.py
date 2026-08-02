from __future__ import annotations

import asyncio
import logging
import sys
from contextlib import suppress

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from redis.asyncio import from_url

from .challenge_repository import ChallengeRepository
from .coaching_repository import CoachingRepository
from .config import Settings
from .cosmetic_repository import CosmeticRepository
from .database import Database
from .guard import RequestGuard
from .handlers import router as core_router
from .league_repository import LeagueRepository
from .llm import JudgeEngine
from .moderation_repository import ModerationRepository
from .privacy import PrivacyConfirmationStore
from .progression_repository import ProgressionRepository
from .pvp_judge import PvPJudgeEngine
from .pvp_repository import PvPRepository
from .pvp_timeout import run_timeout_sweeper
from .ranked_pvp_store import RankedPvPStore
from .ranked_reward_repository import RankedRewardRepository
from .social_repository import SocialRepository
from .sql_profile_store import SQLProfileStore
from .storage import RedisStore
from .v03_engine import V03DebateEngine
from .v03_handlers import router as v03_router
from .v04_handlers import router as v04_router
from .v05_handlers import router as v05_router
from .v06_handlers import router as v06_router
from .v07_handlers import router as v07_router
from .v08_handlers import router as v08_router
from .v09_handlers import router as v09_router
from .v10_handlers import router as v10_router
from .v11_handlers import router as v11_router
from .v13_handlers import router as v13_router
from .v14_handlers import router as v14_router


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
            BotCommand(command="duel", description="Создать PvP-приглашение"),
            BotCommand(command="queue", description="Обычный поиск PvP-соперника"),
            BotCommand(command="ranked_queue", description="Рейтинговый подбор по Elo"),
            BotCommand(command="queue_status", description="Состояние PvP-очереди"),
            BotCommand(command="leave_queue", description="Выйти из PvP-очереди"),
            BotCommand(command="rematch_duel", description="Рематч с последним соперником"),
            BotCommand(command="duel_status", description="Состояние PvP-дуэли"),
            BotCommand(command="cancel_duel", description="Отменить PvP до первого хода"),
            BotCommand(command="forfeit", description="Сдаться в PvP-дуэли"),
            BotCommand(command="rating", description="Личный PvP Elo"),
            BotCommand(command="league", description="Моя рейтинговая лига"),
            BotCommand(command="league_top", description="Таблица рейтинговых лиг"),
            BotCommand(command="league_distribution", description="Распределение по лигам"),
            BotCommand(command="ranked_rewards", description="Награды рейтинговых лиг"),
            BotCommand(command="claim_ranked_rewards", description="Получить награды лиг"),
            BotCommand(command="pvp_leaderboard", description="PvP-лидерборд"),
            BotCommand(command="duel_history", description="История PvP-дуэлей"),
            BotCommand(command="pvp_stats", description="Расширенная PvP-аналитика"),
            BotCommand(command="match_review", description="Разбор последнего PvP-матча"),
            BotCommand(command="pvp_coach", description="Тренд PvP-навыков"),
            BotCommand(command="daily", description="Ежедневные PvP-задания"),
            BotCommand(command="daily_claim", description="Получить награды заданий"),
            BotCommand(command="season", description="Сезонный прогресс"),
            BotCommand(command="season_top", description="Лидерборд сезонного прогресса"),
            BotCommand(command="shop", description="Магазин PvP-косметики"),
            BotCommand(command="buy", description="Купить косметический предмет"),
            BotCommand(command="inventory", description="Мой PvP-инвентарь"),
            BotCommand(command="equip", description="Экипировать косметику"),
            BotCommand(command="unequip", description="Снять косметику"),
            BotCommand(command="pvp_profile", description="PvP-карточка игрока"),
            BotCommand(command="profile_visibility", description="Видимость PvP-профиля"),
            BotCommand(command="rivals", description="Главные PvP-соперники"),
            BotCommand(command="head_to_head", description="Личные встречи с игроком"),
            BotCommand(command="challenge", description="Персональный PvP-вызов"),
            BotCommand(command="challenges", description="Входящие и исходящие вызовы"),
            BotCommand(command="accept_challenge", description="Принять PvP-вызов"),
            BotCommand(command="decline_challenge", description="Отклонить PvP-вызов"),
            BotCommand(command="cancel_challenge", description="Отменить свой PvP-вызов"),
            BotCommand(command="block", description="Заблокировать PvP-соперника"),
            BotCommand(command="unblock", description="Убрать пользователя из блок-листа"),
            BotCommand(command="blocked", description="Показать PvP-блок-лист"),
            BotCommand(command="report", description="Пожаловаться на PvP-матч"),
            BotCommand(command="my_reports", description="Мои PvP-жалобы"),
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
    moderation_repository = ModerationRepository(database.sessions)
    progression_repository = ProgressionRepository(
        database.sessions,
        reset_hour_utc=settings.pvp_daily_reset_hour_utc,
        reward_multiplier=settings.pvp_daily_reward_multiplier,
        stats_window_days=settings.pvp_stats_window_days,
    )
    cosmetic_repository = CosmeticRepository(database.sessions)
    social_repository = SocialRepository(database.sessions)
    challenge_repository = ChallengeRepository(
        database.sessions,
        ttl_hours=settings.pvp_challenge_ttl_hours,
    )
    league_repository = LeagueRepository(database.sessions)
    coaching_repository = CoachingRepository(
        database.sessions,
        window_matches=settings.pvp_coach_window_matches,
    )
    ranked_reward_repository = RankedRewardRepository(database.sessions)
    pvp_store = RankedPvPStore(
        redis,
        prefix=settings.redis_prefix,
        match_ttl_seconds=settings.pvp_match_ttl_seconds,
        invitation_ttl_seconds=settings.pvp_invitation_ttl_seconds,
        queue_ttl_seconds=settings.pvp_queue_ttl_seconds,
        turn_timeout_seconds=settings.pvp_turn_timeout_seconds,
        pair_allowed=moderation_repository.pair_allowed,
        ranked_base_elo_gap=settings.pvp_ranked_base_elo_gap,
        ranked_elo_gap_step=settings.pvp_ranked_elo_gap_step,
        ranked_expand_interval_seconds=settings.pvp_ranked_expand_interval_seconds,
        ranked_max_elo_gap=settings.pvp_ranked_max_elo_gap,
    )
    pvp_repository = PvPRepository(
        database.sessions,
        repeat_window_seconds=settings.pvp_repeat_window_seconds,
        max_rated_pair_matches=settings.pvp_max_rated_pair_matches,
    )
    pvp_judge_engine = PvPJudgeEngine(
        api_key=settings.openai_api_key.get_secret_value(),
        model=settings.openai_judge_model or settings.openai_model,
        base_url=settings.openai_base_url,
    )
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
    dispatcher.include_router(v14_router)
    dispatcher.include_router(v13_router)
    dispatcher.include_router(v11_router)
    dispatcher.include_router(v10_router)
    dispatcher.include_router(v09_router)
    dispatcher.include_router(v08_router)
    dispatcher.include_router(v07_router)
    dispatcher.include_router(v06_router)
    dispatcher.include_router(v05_router)
    dispatcher.include_router(v04_router)
    dispatcher.include_router(v03_router)
    dispatcher.include_router(core_router)
    await set_commands(bot)
    timeout_task = asyncio.create_task(
        run_timeout_sweeper(
            bot,
            pvp_store,
            pvp_repository,
            interval_seconds=settings.pvp_timeout_sweep_seconds,
        )
    )

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
            pvp_store=pvp_store,
            pvp_repository=pvp_repository,
            pvp_judge_engine=pvp_judge_engine,
            moderation_repository=moderation_repository,
            progression_repository=progression_repository,
            cosmetic_repository=cosmetic_repository,
            social_repository=social_repository,
            challenge_repository=challenge_repository,
            league_repository=league_repository,
            coaching_repository=coaching_repository,
            ranked_reward_repository=ranked_reward_repository,
            allowed_updates=dispatcher.resolve_used_update_types(),
        )
    finally:
        timeout_task.cancel()
        with suppress(asyncio.CancelledError):
            await timeout_task
        await engine.close()
        await judge_engine.close()
        await pvp_judge_engine.close()
        await store.close()
        await database.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
