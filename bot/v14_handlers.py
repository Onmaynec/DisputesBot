from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from .config import Settings
from .league_models import league_for_rating
from .pvp_invites import _identity
from .ranked_reward_models import REWARD_BY_LEAGUE, RankedRewardsView
from .ranked_reward_repository import RankedRewardRepository

router = Router(name="v14")


def render_ranked_rewards(view: RankedRewardsView) -> str:
    if view.status.is_placement:
        current = (
            f"🧭 Калибровка: {view.games}/{view.status.placement_games} матчей "
            f"(осталось {view.status.placement_remaining})"
        )
        peak = "Награды откроются после калибровки."
    else:
        assert view.status.league is not None
        current = (
            f"Текущая лига: {view.status.league.icon} {view.status.league.name} "
            f"· {view.rating} Elo"
        )
        peak_league = league_for_rating(view.peak_rating)
        peak = (
            f"Лучший Elo сезона: {view.peak_rating} "
            f"({peak_league.icon} {peak_league.name})"
        )

    lines = [
        "🎁 Награды рейтинговых лиг",
        f"Сезон: {view.season}",
        current,
        peak,
        f"Баланс: {view.wallet_tokens} 🪙",
        "",
    ]
    for entry in view.entries:
        if entry.claimed:
            marker = "✅"
            state = "получено"
        elif entry.eligible:
            marker = "🎁"
            state = "доступно"
        else:
            marker = "🔒"
            state = "закрыто"
        league = entry.definition.league
        lines.append(
            f"{marker} {league.icon} {league.name} — "
            f"{entry.definition.tokens} 🪙 · {state}"
        )

    lines.extend(
        [
            "",
            f"Можно получить сейчас: {view.claimable_tokens} 🪙",
            "Получить: /claim_ranked_rewards",
        ]
    )
    return "\n".join(lines)


@router.message(Command("ranked_rewards"))
async def ranked_rewards_command(
    message: Message,
    ranked_reward_repository: RankedRewardRepository,
    settings: Settings,
) -> None:
    if message.from_user is None:
        return
    view = await ranked_reward_repository.view(
        message.from_user.id,
        settings.pvp_season,
    )
    await message.answer(render_ranked_rewards(view))


@router.message(Command("claim_ranked_rewards"))
async def claim_ranked_rewards_command(
    message: Message,
    ranked_reward_repository: RankedRewardRepository,
    settings: Settings,
) -> None:
    if message.from_user is None:
        return
    result = await ranked_reward_repository.claim(
        _identity(message.from_user),
        settings.pvp_season,
    )
    if result.claimed_league_ids:
        labels = [
            (
                f"{REWARD_BY_LEAGUE[league_id].league.icon} "
                f"{REWARD_BY_LEAGUE[league_id].league.name}"
            )
            for league_id in result.claimed_league_ids
        ]
        await message.answer(
            "✅ Рейтинговые награды получены!\n"
            f"Дивизионы: {', '.join(labels)}\n"
            f"Начислено: {result.gained_tokens} 🪙\n"
            f"Новый баланс: {result.wallet_tokens} 🪙"
        )
        return
    if result.view.status.is_placement:
        await message.answer(
            "🧭 Сначала завершите рейтинговую калибровку.\n"
            f"Осталось матчей: {result.view.status.placement_remaining}.\n"
            "Статус наград: /ranked_rewards"
        )
        return
    await message.answer(
        "Новых рейтинговых наград нет. Уже полученные награды не начисляются повторно.\n"
        "Подробности: /ranked_rewards"
    )
