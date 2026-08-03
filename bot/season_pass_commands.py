from __future__ import annotations

from aiogram import Bot, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import BotCommand, Message

from .config import Settings
from .cosmetic_repository import CosmeticRepository
from .cosmetics import SEASON_PASS_COMPLETION_COSMETIC, cosmetic_by_id
from .progression_repository import ProgressionRepository
from .pvp_invites import _identity
from .season_pass_models import SeasonPassDashboard, tier_for_id
from .season_pass_repository import SeasonPassRepository

router = Router(name="season_pass")


async def register_v22_commands(bot: Bot) -> None:
    commands = await bot.get_my_commands()
    existing = {item.command for item in commands}
    additions = [
        BotCommand(command="season_pass", description="Сезонный пропуск и награды"),
        BotCommand(
            command="claim_season_pass",
            description="Получить награды сезонного пропуска",
        ),
        BotCommand(
            command="pass_collection",
            description="Эксклюзивная косметика пропуска",
        ),
    ]
    merged = [*commands, *(item for item in additions if item.command not in existing)]
    if len(merged) != len(commands):
        await bot.set_my_commands(merged)


router.startup.register(register_v22_commands)


PRIVACY_TEXT = """🔐 Приватность DisputesBot v0.22

Постоянно сохраняются Telegram user_id, имя профиля, статистика и архивы дебатов,
сезонный PvP Elo, завершённые матчи, судейские оценки полных матчей, blocklist,
жалобы, progression wallet, daily claims, ranked rewards, косметика, настройки
публичности, персональные вызовы, приватные сезонные цели и claims наград целей.

Сезонный пропуск использует только уже сохранённые season points. После claim хранится
аудиторская строка с user ID, сезоном, tier ID, требованием по очкам, числом токенов,
balance season points в момент claim, точным cosmetic item ID и временем выдачи.
Темы, аргументы, стенограммы, вердикты и judge-score payload туда не копируются.

/season_pass, /claim_season_pass и /pass_collection доступны только владельцу
Telegram user ID. Один уровень можно получить только один раз за сезон. После выдачи
всех семи уровней бот добавляет финальный титул «Хранитель сезона» в ту же
транзакцию. Финальная награда не начисляет токены или season points, не меняет Elo,
matchmaking, судейство или исход матча.

После обновления старые claims v0.20 могут получить отсутствующую tier-косметику, а
полностью закрытый пропуск v0.21 — финальный титул без повторного начисления токенов.
Предметы пропуска нельзя купить через /buy. Они находятся в том же сезонном
инвентаре, поддерживают /equip и могут отображаться в PvP-профиле.

Приватные goals, coaching, recap, comparison и record-book отчёты другим игрокам не
показываются. Публичные команды используют только разрешённые агрегаты профиля.

В Redis временно находятся активные споры и PvP-матчи, приглашения, очереди,
Elo-снимки matchmaking, дедлайны, rate limit, request locks и подтверждение удаления.

/delete_me удаляет профиль, архивы, PvP-рейтинг и матчи, progression-данные,
ranked rewards, сезонные цели, goal reward claims, season-pass claims и выданную
косметику, публичность, вызовы, blocklist, очереди, настройки и активные Redis-сессии.
Claims и inventory используют ON DELETE CASCADE. Жалобы сохраняются как обезличенные
аудиторские записи."""


def _progress_bar(progress: float) -> str:
    filled = max(0, min(10, round(progress * 10)))
    return "█" * filled + "░" * (10 - filled)


def _completion_status(dashboard: SeasonPassDashboard) -> tuple[str, str]:
    if dashboard.completion_cosmetic_owned:
        return "✅", "получено"
    if dashboard.completion_reward_claimable:
        return "🎁", "получить: /claim_season_pass"
    return "🔒", f"закройте уровни: {dashboard.claimed_count}/{len(dashboard.tiers)}"


def render_season_pass(dashboard: SeasonPassDashboard) -> str:
    lines = [
        "🎟 Сезонный пропуск",
        f"Сезон: {dashboard.season}",
        f"Прогресс: {dashboard.season_points} очков",
        f"Кошелёк: {dashboard.wallet_tokens} 🪙",
        f"Доступно: {dashboard.claimable_count}",
        f"Коллекция: {dashboard.collection_count}/{dashboard.collection_total}",
        "",
    ]
    for view in dashboard.tiers:
        tier = view.tier
        cosmetic = tier.reward_cosmetic
        if view.is_claimed:
            marker = "✅"
            status = "получено"
        elif view.is_claimable and view.token_claimed:
            marker = "🎨"
            status = "косметика доступна"
        elif view.is_claimable:
            marker = "🎁"
            status = "можно получить"
        else:
            marker = "🔒"
            status = f"нужно ещё {max(0, tier.points_required - dashboard.season_points)}"
        lines.append(f"{marker} {tier.icon} {tier.name} · {tier.points_required} очков")
        lines.append(
            f"Награда: {tier.reward_tokens} 🪙 + "
            f"{cosmetic.display} {cosmetic.name} · {status}"
        )
        if not view.is_unlocked:
            lines.append(f"{_progress_bar(view.progress)} {view.progress_percent}%")
        lines.append("")

    completion = dashboard.completion_cosmetic
    marker, status = _completion_status(dashboard)
    lines.append(f"{marker} 🌟 Финал коллекции")
    lines.append(f"Награда: {completion.display} {completion.name} · {status}")
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
            "Коллекция эксклюзивов: /pass_collection",
            "Награды пропуска не добавляют season points.",
        ]
    )
    return "\n".join(lines)


def _repository(progression_repository: ProgressionRepository) -> SeasonPassRepository:
    return SeasonPassRepository(progression_repository.sessions)


@router.message(CommandStart())
async def start_v22_command(message: Message) -> None:
    await message.answer(
        "⚔️ Добро пожаловать в DisputesBot v0.22!\n\n"
        "Новые возможности:\n"
        "/season_pass — уровни, токены и финальная награда\n"
        "/claim_season_pass — получить все разблокированные награды\n"
        "/pass_collection — коллекция из восьми эксклюзивов\n\n"
        "За полное закрытие пропуска выдаётся титул «Хранитель сезона».\n\n"
        "Награды целей: /goal_rewards · /claim_goal_rewards\n"
        "Цели: /goals · /set_goal · /goal_suggest\n"
        "Итоги: /season_recap · /compare_seasons · /career_records\n"
        "Начать спор: /debate [тема]"
    )


@router.message(Command("privacy"))
async def privacy_v22_command(message: Message) -> None:
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
    if not result.changed:
        await message.answer(
            "Новых наград нет. Набирайте season points и проверяйте /season_pass."
        )
        return

    lines = ["🎟 Награды сезонного пропуска получены!"]
    if result.claimed_tier_ids:
        labels = ", ".join(
            tier_for_id(tier_id).name for tier_id in result.claimed_tier_ids
        )
        lines.append(f"Новые уровни: {labels}")
        lines.append(f"Начислено: +{result.gained_tokens} 🪙")
    if result.granted_cosmetic_ids:
        cosmetic_labels = []
        for item_id in result.granted_cosmetic_ids:
            item = cosmetic_by_id(item_id)
            cosmetic_labels.append(
                f"{item.display} {item.name}" if item is not None else item_id
            )
        lines.append(f"Косметика: {', '.join(cosmetic_labels)}")
    if SEASON_PASS_COMPLETION_COSMETIC.item_id in result.granted_cosmetic_ids:
        lines.append("🌟 Пропуск закрыт полностью — финальный титул разблокирован.")
    if result.auto_equipped_ids:
        lines.append("Первый предмет в свободном слоте экипирован автоматически.")
    lines.append(
        f"Баланс: {result.wallet_tokens} 🪙 · {result.season_points} очков"
    )
    await message.answer("\n".join(lines))


@router.message(Command("pass_collection"))
async def pass_collection_command(
    message: Message,
    progression_repository: ProgressionRepository,
    cosmetic_repository: CosmeticRepository,
    settings: Settings,
) -> None:
    if message.from_user is None:
        return
    dashboard = await _repository(progression_repository).dashboard(
        message.from_user.id,
        settings.pvp_season,
    )
    inventory = await cosmetic_repository.inventory(
        message.from_user.id,
        settings.pvp_season,
    )
    equipped = {inventory.equipped_badge_id, inventory.equipped_title_id}
    lines = [
        "🎨 Коллекция сезонного пропуска",
        f"Сезон: {dashboard.season}",
        f"Получено: {dashboard.collection_count}/{dashboard.collection_total}",
        "",
    ]
    for view in dashboard.tiers:
        item = view.tier.reward_cosmetic
        if item.item_id in equipped:
            marker = "🎖"
            status = "экипировано"
        elif item.item_id in inventory.owned_item_ids:
            marker = "✅"
            status = "в инвентаре"
        elif view.is_unlocked:
            marker = "🎁"
            status = "получить: /claim_season_pass"
        else:
            marker = "🔒"
            status = f"{view.tier.points_required} очков"
        lines.append(
            f"{marker} {item.display} {item.name} (`{item.item_id}`) — {status}"
        )

    completion = dashboard.completion_cosmetic
    if completion.item_id in equipped:
        marker = "🎖"
        status = "экипировано"
    elif completion.item_id in inventory.owned_item_ids:
        marker = "✅"
        status = "в инвентаре"
    elif dashboard.completion_reward_claimable:
        marker = "🎁"
        status = "получить: /claim_season_pass"
    else:
        marker = "🔒"
        status = f"закройте уровни: {dashboard.claimed_count}/{len(dashboard.tiers)}"
    lines.extend(
        [
            "",
            "🌟 Финальная награда",
            f"{marker} {completion.display} {completion.name} "
            f"(`{completion.item_id}`) — {status}",
            "",
            "Экипировать предмет: /equip item_id",
        ]
    )
    await message.answer("\n".join(lines), parse_mode="Markdown")
