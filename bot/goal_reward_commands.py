from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

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
