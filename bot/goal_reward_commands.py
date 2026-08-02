from __future__ import annotations

from aiogram import Bot, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import BotCommand, Message

from .config import Settings
from .goal_reward_models import GoalRewardDashboard, GoalRewardView
from .goal_reward_repository import GoalRewardRepository
from .pvp_invites import _identity
from .season_goal_models import (
    GoalMetric,
    definition_for,
    format_metric_value,
)
from .season_goal_repository import SeasonGoalRepository

router = Router(name="goal_rewards")


async def register_v19_commands(bot: Bot) -> None:
    commands = await bot.get_my_commands()
    existing = {item.command for item in commands}
    additions = [
        BotCommand(command="goal_rewards", description="Награды сезонных PvP-целей"),
        BotCommand(
            command="claim_goal_rewards",
            description="Получить награды выполненных целей",
        ),
    ]
    merged = [*commands, *(item for item in additions if item.command not in existing)]
    if len(merged) != len(commands):
        await bot.set_my_commands(merged)


router.startup.register(register_v19_commands)


PRIVACY_TEXT = """🔐 Приватность DisputesBot v0.19

Постоянно сохраняются Telegram user_id, имя профиля, статистика и архивы дебатов,
сезонный PvP Elo, завершённые матчи, судейские оценки полных матчей, blocklist,
жалобы, progression wallet, daily claims, ranked rewards, косметика, настройки
публичности, персональные вызовы и приватные сезонные цели.

Награды целей хранят отдельную audit-строку только после claim: user ID, сезон,
фиксированный ID метрики, числовые baseline и target, число токенов и очков, время
выполнения и получения. Свободный текст, темы матчей, аргументы, стенограммы,
вердикты и judge score payload в reward claim не копируются.

/goals, /goal_rewards и /claim_goal_rewards доступны только владельцу Telegram user ID.
Одна метрика может дать награду только один раз за сезон. Claim не меняет Elo,
matchmaking, судейство или результат матча; он добавляет только токены и season points
в существующий progression wallet.

Публичные команды используют только ранее разрешённые агрегаты профиля. Приватные
coaching, recap, comparison, record book и goal-отчёты другим игрокам не показываются.

В Redis временно находятся активные споры и PvP-матчи, приглашения, очереди,
Elo-снимки matchmaking, дедлайны, rate limit, request locks и подтверждение удаления.

/delete_me удаляет профиль, архивы, PvP-рейтинг и матчи, progression-данные,
ranked reward claims, сезонные цели и goal reward claims, косметику, публичность,
вызовы, blocklist, очереди, настройки и активные Redis-сессии. Goal reward claims
также используют ON DELETE CASCADE от профиля. Жалобы сохраняются как обезличенные
аудиторские записи."""


def _baseline(goal: GoalRewardView) -> str:
    if goal.metric is GoalMetric.LEAGUE:
        return f"{round(goal.baseline_value)} Elo"
    return format_metric_value(goal.metric, goal.baseline_value)


def _delta(goal: GoalRewardView, value: float) -> str:
    if goal.metric in {GoalMetric.ELO, GoalMetric.LEAGUE}:
        return f"+{round(value)} Elo"
    if goal.metric is GoalMetric.WIN_RATE:
        return f"+{value:.1f} п.п."
    if goal.metric in {GoalMetric.LOGIC, GoalMetric.EVIDENCE, GoalMetric.REBUTTAL}:
        return f"+{value:.1f}"
    return f"+{round(value)}"


def _status(goal: GoalRewardView) -> str:
    if goal.is_claimed:
        return "✅ Награда получена"
    if goal.is_claimable:
        return "🎁 Можно получить"
    if goal.is_completed and not goal.qualifies:
        return (
            "▫️ Личная цель: для награды нужен прирост "
            f"не меньше {_delta(goal, goal.minimum_delta)}"
        )
    return "⏳ Цель ещё не завершена"


def render_goal_rewards(dashboard: GoalRewardDashboard) -> str:
    lines = [
        "🎁 Награды сезонных целей",
        f"Сезон: {dashboard.season}",
        f"Кошелёк: {dashboard.wallet_tokens} 🪙 · {dashboard.wallet_points} очков",
        f"Доступно: {dashboard.claimable_count} · получено: {dashboard.claimed_count}",
        "",
    ]
    if not dashboard.rewards:
        lines.extend(
            [
                "Сезонных целей пока нет.",
                "Создать цель: /set_goal elo 1200",
                "Подсказки: /goal_suggest",
            ]
        )
        return "\n".join(lines)

    for goal in dashboard.rewards:
        definition = definition_for(goal.metric)
        lines.append(f"{definition.icon} {definition.label}")
        lines.append(
            f"{_baseline(goal)} → {format_metric_value(goal.metric, goal.target_value)} "
            f"({_delta(goal, goal.challenge_delta)})"
        )
        lines.append(f"Награда: {goal.reward_tokens} 🪙 · {goal.reward_points} очков")
        lines.append(_status(goal))
        lines.append("")
    lines.extend(
        [
            "Получить всё доступное: /claim_goal_rewards",
            "Одна метрика выдаёт награду только один раз за сезон.",
        ]
    )
    return "\n".join(lines)


def _reward_repository(
    season_goal_repository: SeasonGoalRepository,
) -> GoalRewardRepository:
    return GoalRewardRepository(
        season_goal_repository.sessions,
        season_goal_repository=season_goal_repository,
    )


@router.message(CommandStart())
async def start_v19_command(message: Message) -> None:
    await message.answer(
        "⚔️ Добро пожаловать в DisputesBot v0.19!\n\n"
        "Новые команды:\n"
        "/goal_rewards — награды и требования текущих целей\n"
        "/claim_goal_rewards — получить все доступные токены и очки\n\n"
        "Цели: /goals · /set_goal · /goal_suggest\n"
        "Итоги: /season_recap · /compare_seasons · /career_records\n"
        "Рекорды: /pvp_records · /season_records\n"
        "Начать спор: /debate [тема]"
    )


@router.message(Command("privacy"))
async def privacy_v19_command(message: Message) -> None:
    await message.answer(PRIVACY_TEXT)


@router.message(Command("goal_rewards"))
async def goal_rewards_command(
    message: Message,
    season_goal_repository: SeasonGoalRepository,
    settings: Settings,
) -> None:
    if message.from_user is None:
        return
    dashboard = await _reward_repository(season_goal_repository).dashboard(
        message.from_user.id,
        settings.pvp_season,
    )
    await message.answer(render_goal_rewards(dashboard))


@router.message(Command("claim_goal_rewards"))
async def claim_goal_rewards_command(
    message: Message,
    season_goal_repository: SeasonGoalRepository,
    settings: Settings,
) -> None:
    if message.from_user is None:
        return
    result = await _reward_repository(season_goal_repository).claim(
        _identity(message.from_user),
        settings.pvp_season,
    )
    if not result.claimed_metrics:
        await message.answer(
            "Новых наград нет. Завершите значимую цель и проверьте /goal_rewards."
        )
        return
    labels = ", ".join(
        definition_for(metric).label for metric in result.claimed_metrics
    )
    await message.answer(
        "🎁 Награды получены!\n"
        f"Цели: {labels}\n"
        f"Начислено: +{result.gained_tokens} 🪙 · +{result.gained_points} очков\n"
        f"Баланс: {result.wallet_tokens} 🪙 · {result.wallet_points} очков"
    )
