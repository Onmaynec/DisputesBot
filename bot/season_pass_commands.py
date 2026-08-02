from __future__ import annotations

from aiogram import Bot, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import BotCommand, Message

from .config import Settings
from .progression_repository import ProgressionRepository
from .pvp_invites import _identity
from .season_pass_models import SeasonPassDashboard, tier_for_id
from .season_pass_repository import SeasonPassRepository

router = Router(name="season_pass")


async def register_v20_commands(bot: Bot) -> None:
    commands = await bot.get_my_commands()
    existing = {item.command for item in commands}
    additions = [
        BotCommand(command="season_pass", description="Сезонный пропуск и награды"),
        BotCommand(
            command="claim_season_pass",
            description="Получить награды сезонного пропуска",
        ),
    ]
    merged = [*commands, *(item for item in additions if item.command not in existing)]
    if len(merged) != len(commands):
        await bot.set_my_commands(merged)


router.startup.register(register_v20_commands)


PRIVACY_TEXT = """🔐 Приватность DisputesBot v0.20

Постоянно сохраняются Telegram user_id, имя профиля, статистика и архивы дебатов,
сезонный PvP Elo, завершённые матчи, судейские оценки полных матчей, blocklist,
жалобы, progression wallet, daily claims, ranked rewards, косметика, настройки
публичности, персональные вызовы, приватные сезонные цели и claims наград целей.

Сезонный пропуск использует только уже сохранённые season points. После claim хранится
аудиторская строка с user ID, сезоном, фиксированным tier ID, требованием по очкам,
числом токенов, балансом season points в момент claim и временем операции. Темы,
аргументы, стенограммы, вердикты и judge-score payload туда не копируются.

/season_pass и /claim_season_pass доступны только владельцу Telegram user ID.
Один уровень можно получить только один раз за сезон. Награда добавляет только токены:
она не начисляет season points, не меняет Elo, matchmaking, судейство или исход матча.

Награды целей используют числовые baseline/target и фиксированный ID метрики.
Приватные goals, coaching, recap, comparison и record-book отчёты другим игрокам
не показываются. Публичные команды используют только разрешённые агрегаты профиля.

В Redis временно находятся активные споры и PvP-матчи, приглашения, очереди,
Elo-снимки matchmaking, дедлайны, rate limit, request locks и подтверждение удаления.

/delete_me удаляет профиль, архивы, PvP-рейтинг и матчи, progression-данные,
ranked rewards, сезонные цели, goal reward claims, season-pass claims, косметику,
публичность, вызовы, blocklist, очереди, настройки и активные Redis-сессии.
Season-pass claims также используют ON DELETE CASCADE от профиля. Жалобы сохраняются
как обезличенные аудиторские записи."""


def _progress_bar(progress: float) -> str:
    filled = max(0, min(10, round(progress * 10)))
    return "█" * filled + "░" * (10 - filled)


def render_season_pass(dashboard: SeasonPassDashboard) -> str:
    lines = [
        "🎟 Сезонный пропуск",
        f"Сезон: {dashboard.season}",
        f"Прогресс: {dashboard.season_points} очков",
        f"Кошелёк: {dashboard.wallet_tokens} 🪙",
        f"Доступно: {dashboard.claimable_count} · получено: {dashboard.claimed_count}",
        "",
    ]
    for view in dashboard.tiers:
        tier = view.tier
        if view.is_claimed:
            marker = "✅"
            status = "получено"
        elif view.is_claimable:
            marker = "🎁"
            status = "можно получить"
        else:
            marker = "🔒"
            status = f"нужно ещё {max(0, tier.points_required - dashboard.season_points)}"
        lines.append(f"{marker} {tier.icon} {tier.name} · {tier.points_required} очков")
        lines.append(f"Награда: {tier.reward_tokens} 🪙 · {status}")
        if not view.is_unlocked:
            lines.append(f"{_progress_bar(view.progress)} {view.progress_percent}%")
        lines.append("")

    next_tier = dashboard.next_tier
    if next_tier is None:
        lines.append("🏆 Все уровни сезонного пропуска разблокированы.")
    else:
        remaining = next_tier.tier.points_required - dashboard.season_points
        lines.append(
            f"Следующий уровень: {next_tier.tier.icon} {next_tier.tier.name} "
            f"через {remaining} очков."
        )
    lines.extend(
        [
            "Получить всё доступное: /claim_season_pass",
            "Награды пропуска не добавляют season points.",
        ]
    )
    return "\n".join(lines)


def _repository(progression_repository: ProgressionRepository) -> SeasonPassRepository:
    return SeasonPassRepository(progression_repository.sessions)


@router.message(CommandStart())
async def start_v20_command(message: Message) -> None:
    await message.answer(
        "⚔️ Добро пожаловать в DisputesBot v0.20!\n\n"
        "Новые команды:\n"
        "/season_pass — уровни сезонного пропуска и прогресс\n"
        "/claim_season_pass — получить все разблокированные токены\n\n"
        "Награды целей: /goal_rewards · /claim_goal_rewards\n"
        "Цели: /goals · /set_goal · /goal_suggest\n"
        "Итоги: /season_recap · /compare_seasons · /career_records\n"
        "Начать спор: /debate [тема]"
    )


@router.message(Command("privacy"))
async def privacy_v20_command(message: Message) -> None:
    await message.answer(PRIVACY_TEXT)


@router.message(Command("season_pass"))
async def season_pass_command(
    message: Message,
    progression_repository: ProgressionRepository,
    settings: Settings,
) -> None:
    if message.from_user is None:
        return
    dashboard = await _repository(progression_repository).dashboard(
        message.from_user.id,
        settings.pvp_season,
    )
    await message.answer(render_season_pass(dashboard))


@router.message(Command("claim_season_pass"))
async def claim_season_pass_command(
    message: Message,
    progression_repository: ProgressionRepository,
    settings: Settings,
) -> None:
    if message.from_user is None:
        return
    result = await _repository(progression_repository).claim(
        _identity(message.from_user),
        settings.pvp_season,
    )
    if not result.claimed_tier_ids:
        await message.answer(
            "Новых наград нет. Набирайте season points и проверяйте /season_pass."
        )
        return
    labels = ", ".join(tier_for_id(tier_id).name for tier_id in result.claimed_tier_ids)
    await message.answer(
        "🎟 Награды сезонного пропуска получены!\n"
        f"Уровни: {labels}\n"
        f"Начислено: +{result.gained_tokens} 🪙\n"
        f"Баланс: {result.wallet_tokens} 🪙 · {result.season_points} очков"
    )
