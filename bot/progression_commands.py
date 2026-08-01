from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from .config import Settings
from .cosmetics_repository import CosmeticsRepository
from .progression_models import season_tier
from .progression_repository import ProgressionRepository
from .pvp_models import PvPUser

router = Router(name="progression")


@router.message(Command("daily"))
async def daily_command(
    message: Message,
    progression_repository: ProgressionRepository,
    settings: Settings,
) -> None:
    if message.from_user is None:
        return
    view = await progression_repository.daily_progress(
        message.from_user.id,
        settings.pvp_season,
    )
    lines = [
        f"🎯 Ежедневные задания — {view.day.isoformat()}",
        f"Сброс: {settings.pvp_daily_reset_hour_utc:02d}:00 UTC",
        "",
    ]
    for index, quest in enumerate(view.quests, start=1):
        if quest.claimed:
            icon = "✅"
            status = "награда получена"
        elif quest.completed:
            icon = "🎁"
            status = "готово — /daily_claim"
        else:
            icon = "⏳"
            status = f"осталось {quest.remaining}"
        lines.append(
            f"{icon} {index}. {quest.definition.title}\n"
            f"   {quest.progress}/{quest.definition.target} · "
            f"{quest.definition.reward_tokens * settings.pvp_daily_reward_multiplier} "
            f"токенов · "
            f"{quest.definition.reward_points * settings.pvp_daily_reward_multiplier} "
            f"очков · {status}"
        )
    lines.extend(
        [
            "",
            f"🪙 Токены: {view.wallet.tokens}",
            f"⭐ Очки сезона: {view.wallet.season_points}",
            f"🔥 Серия дней: {view.wallet.current_daily_streak}",
        ]
    )
    await message.answer("\n".join(lines))


@router.message(Command("daily_claim"))
async def daily_claim_command(
    message: Message,
    progression_repository: ProgressionRepository,
    settings: Settings,
) -> None:
    if message.from_user is None:
        return
    user = PvPUser(
        user_id=message.from_user.id,
        username=message.from_user.username,
        display_name=message.from_user.full_name,
    )
    result = await progression_repository.claim_daily(user, settings.pvp_season)
    if not result.claimed_quest_ids:
        await message.answer(
            "Новых наград нет. Проверьте прогресс командой /daily."
        )
        return
    await message.answer(
        "🎁 Награды получены!\n\n"
        f"Заданий: {len(result.claimed_quest_ids)}\n"
        f"🪙 +{result.gained_tokens} токенов\n"
        f"⭐ +{result.gained_points} очков сезона\n"
        f"🔥 Серия дней: {result.wallet.current_daily_streak}\n"
        f"🏆 Лучшая серия: {result.wallet.best_daily_streak}"
    )


@router.message(Command("season"))
async def season_command(
    message: Message,
    progression_repository: ProgressionRepository,
    cosmetics_repository: CosmeticsRepository,
    settings: Settings,
) -> None:
    if message.from_user is None:
        return
    wallet = await progression_repository.wallet(
        message.from_user.id,
        settings.pvp_season,
    )
    title = await cosmetics_repository.equipped_title(
        message.from_user.id,
        settings.pvp_season,
    )
    tier = season_tier(wallet.season_points)
    title_text = title.label if title is not None else "не выбран"
    await message.answer(
        f"🏅 Сезонный прогресс — {settings.pvp_season}\n\n"
        f"Титул: {title_text}\n"
        f"Уровень {tier.number}: {tier.name}\n"
        f"Прогресс уровня: {tier.progress_text(wallet.season_points)}\n"
        f"⭐ Очки сезона: {wallet.season_points}\n"
        f"🪙 PvP-токены: {wallet.tokens}\n"
        f"🎯 Получено заданий: {wallet.daily_claims}\n"
        f"🔥 Текущая серия: {wallet.current_daily_streak}\n"
        f"🏆 Лучшая серия: {wallet.best_daily_streak}\n\n"
        "Магазин титулов: /shop"
    )


@router.message(Command("season_top"))
async def season_top_command(
    message: Message,
    progression_repository: ProgressionRepository,
    settings: Settings,
) -> None:
    entries = await progression_repository.top(settings.pvp_season, limit=10)
    if not entries:
        await message.answer(
            "Сезонный лидерборд пока пуст. Выполняйте задания через /daily."
        )
        return
    lines = [f"🏆 Сезонный прогресс — {settings.pvp_season}", ""]
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    for position, entry in enumerate(entries, start=1):
        prefix = medals.get(position, f"{position}.")
        lines.append(
            f"{prefix} {entry.display_name} — {entry.season_points} ⭐ · "
            f"{entry.tokens} 🪙 · серия {entry.current_daily_streak}"
        )
    await message.answer("\n".join(lines))


@router.message(Command("pvp_stats"))
async def pvp_stats_command(
    message: Message,
    progression_repository: ProgressionRepository,
    settings: Settings,
) -> None:
    if message.from_user is None:
        return
    stats = await progression_repository.analytics(
        message.from_user.id,
        settings.pvp_season,
    )
    rating = str(stats.rating) if stats.rating is not None else "нет матчей"
    rank = f"#{stats.rank}" if stats.rank is not None else "—"
    await message.answer(
        f"📊 PvP-аналитика — {settings.pvp_season}\n\n"
        f"Elo: {rating} · место: {rank}\n"
        f"Матчи: {stats.total_matches} "
        f"({stats.rated_matches} рейтинговых / {stats.unrated_matches} нерейтинговых)\n"
        f"Победы / ничьи / поражения: "
        f"{stats.wins} / {stats.draws} / {stats.losses}\n"
        f"Win rate: {stats.win_rate}%\n"
        f"Уникальные соперники: {stats.unique_opponents}\n"
        f"Изменение Elo за {stats.window_days} дней: "
        f"{stats.rating_delta_window:+d}\n"
        f"Серия побед: {stats.current_win_streak} "
        f"(лучшая {stats.best_win_streak})\n"
        f"За: {stats.pro_wins}/{stats.pro_matches} побед · "
        f"Против: {stats.con_wins}/{stats.con_matches} побед"
    )
