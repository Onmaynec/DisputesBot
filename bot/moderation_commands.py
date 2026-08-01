from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from .config import Settings
from .moderation_models import ReportCategory, ReportStatus
from .moderation_repository import ModerationRepository
from .pvp_invites import _identity
from .pvp_repository import PvPRepository
from .pvp_store import PvPStore

router = Router(name="v06-moderation")

_CATEGORY_ALIASES = {
    "abuse": ReportCategory.ABUSE,
    "оскорбления": ReportCategory.ABUSE,
    "spam": ReportCategory.SPAM,
    "спам": ReportCategory.SPAM,
    "cheating": ReportCategory.CHEATING,
    "обход": ReportCategory.CHEATING,
    "обход_правил": ReportCategory.CHEATING,
    "other": ReportCategory.OTHER,
    "другое": ReportCategory.OTHER,
}


def _is_moderator(user_id: int, settings: Settings) -> bool:
    return user_id in settings.moderator_ids


def _target_from_message(message: Message, command: CommandObject) -> tuple[int, str] | None:
    if message.reply_to_message and message.reply_to_message.from_user:
        user = message.reply_to_message.from_user
        return user.id, user.full_name
    raw = (command.args or "").strip().split(maxsplit=1)[0]
    if raw.isdigit():
        user_id = int(raw)
        return user_id, f"user_id {user_id}"
    return None


@router.message(Command("block"))
async def block_command(
    message: Message,
    command: CommandObject,
    moderation_repository: ModerationRepository,
    pvp_store: PvPStore,
) -> None:
    if message.from_user is None:
        return
    target = _target_from_message(message, command)
    if target is None:
        await message.answer(
            "Ответьте на сообщение пользователя командой /block или укажите /block user_id."
        )
        return
    target_id, target_label = target
    try:
        created = await moderation_repository.block_user(
            _identity(message.from_user),
            target_id,
            blocked_label=target_label,
        )
    except ValueError as exc:
        await message.answer(str(exc))
        return
    await pvp_store.clear_pending(message.from_user.id)
    text = "добавлен в блок-лист" if created else "уже был в блок-листе"
    await message.answer(f"🚫 {target_label} {text}. Новые PvP-матчи этой пары запрещены.")


@router.message(Command("unblock"))
async def unblock_command(
    message: Message,
    command: CommandObject,
    moderation_repository: ModerationRepository,
) -> None:
    if message.from_user is None:
        return
    raw = (command.args or "").strip()
    if not raw.isdigit():
        await message.answer("Укажите Telegram user_id: /unblock 123456789")
        return
    removed = await moderation_repository.unblock_user(message.from_user.id, int(raw))
    await message.answer(
        "✅ Пользователь удалён из блок-листа."
        if removed
        else "Такого пользователя не было в блок-листе."
    )


@router.message(Command("blocked"))
async def blocked_command(
    message: Message,
    moderation_repository: ModerationRepository,
) -> None:
    if message.from_user is None:
        return
    entries = await moderation_repository.list_blocks(message.from_user.id)
    if not entries:
        await message.answer("Ваш PvP-блок-лист пуст.")
        return
    lines = ["🚫 Заблокированные PvP-соперники:"]
    for item in entries[:20]:
        lines.append(f"• {item.label} — `{item.user_id}`")
    lines.append("\nРазблокировать: /unblock user_id")
    await message.answer("\n".join(lines), parse_mode="Markdown")


@router.message(Command("report"))
async def report_command(
    message: Message,
    command: CommandObject,
    moderation_repository: ModerationRepository,
    pvp_store: PvPStore,
    pvp_repository: PvPRepository,
) -> None:
    if message.from_user is None:
        return
    parts = (command.args or "").strip().split(maxsplit=1)
    if not parts or parts[0].casefold() not in _CATEGORY_ALIASES:
        await message.answer(
            "Использование: /report [оскорбления|спам|обход_правил|другое] [комментарий]"
        )
        return
    category = _CATEGORY_ALIASES[parts[0].casefold()]
    comment = parts[1] if len(parts) > 1 else ""
    active = await pvp_store.get_match_for_user(message.from_user.id)
    try:
        if active is not None:
            created, report = await moderation_repository.create_report(
                reporter_id=message.from_user.id,
                category=category,
                comment=comment,
                match=active,
            )
        else:
            history = await pvp_repository.history(message.from_user.id, limit=1)
            if not history:
                await message.answer("Нет PvP-матча, на который можно отправить жалобу.")
                return
            created, report = await moderation_repository.create_report(
                reporter_id=message.from_user.id,
                category=category,
                comment=comment,
                match_id=history[0].match_id,
            )
    except ValueError as exc:
        await message.answer(f"Жалоба не создана: {exc}")
        return
    label = "создана" if created else "уже существует"
    await message.answer(
        f"🛡 Жалоба {label}. ID: `{report.report_id}`\n"
        "Она не изменяет результат матча или Elo.",
        parse_mode="Markdown",
    )


@router.message(Command("my_reports"))
async def my_reports_command(
    message: Message,
    moderation_repository: ModerationRepository,
) -> None:
    if message.from_user is None:
        return
    reports = await moderation_repository.my_reports(message.from_user.id)
    if not reports:
        await message.answer("У вас нет PvP-жалоб.")
        return
    lines = ["🛡 Ваши жалобы:"]
    for report in reports:
        lines.append(
            f"• {report.category.value} · {report.status.value} · "
            f"{report.match_topic[:60]} · `{report.report_id}`"
        )
    await message.answer("\n".join(lines), parse_mode="Markdown")


@router.message(Command("admin_reports"))
async def admin_reports_command(
    message: Message,
    command: CommandObject,
    moderation_repository: ModerationRepository,
    settings: Settings,
) -> None:
    if message.from_user is None or not _is_moderator(message.from_user.id, settings):
        await message.answer("Команда недоступна.")
        return
    raw_status = (command.args or ReportStatus.OPEN.value).strip().casefold()
    try:
        status = ReportStatus(raw_status)
    except ValueError:
        await message.answer("Статус: open, resolved или rejected.")
        return
    reports = await moderation_repository.list_reports(status)
    if not reports:
        await message.answer(f"Жалоб со статусом {status.value} нет.")
        return
    lines = [f"🛡 Жалобы: {status.value}"]
    for report in reports:
        lines.append(
            f"• `{report.report_id}` · {report.category.value} · "
            f"match `{report.match_id}` · reporter {report.reporter_id or 'deleted'}"
        )
    await message.answer("\n".join(lines), parse_mode="Markdown")


@router.message(Command("resolve_report"))
async def resolve_report_command(
    message: Message,
    command: CommandObject,
    moderation_repository: ModerationRepository,
    settings: Settings,
) -> None:
    if message.from_user is None or not _is_moderator(message.from_user.id, settings):
        await message.answer("Команда недоступна.")
        return
    parts = (command.args or "").strip().split(maxsplit=2)
    if len(parts) < 2:
        await message.answer(
            "Использование: /resolve_report report_id [resolved|rejected] [заметка]"
        )
        return
    report_id, raw_status = parts[:2]
    note = parts[2] if len(parts) > 2 else ""
    try:
        status = ReportStatus(raw_status.casefold())
        changed, report = await moderation_repository.resolve_report(
            report_id,
            status=status,
            moderator_id=message.from_user.id,
            note=note,
        )
    except ValueError as exc:
        await message.answer(str(exc))
        return
    if report is None:
        await message.answer("Жалоба не найдена.")
        return
    await message.answer(
        f"✅ Статус: {report.status.value}."
        if changed
        else f"Статус уже был {report.status.value}."
    )


@router.message(Command("pvp_health"))
async def pvp_health_command(
    message: Message,
    moderation_repository: ModerationRepository,
    pvp_store: PvPStore,
    settings: Settings,
) -> None:
    if message.from_user is None or not _is_moderator(message.from_user.id, settings):
        await message.answer("Команда недоступна.")
        return
    active, queued, reports = await _health_counts(
        pvp_store,
        moderation_repository,
    )
    await message.answer(
        "🩺 PvP health\n\n"
        f"Активные матчи: {active}\n"
        f"Очередь: {queued}\n"
        f"Открытые жалобы: {reports}\n"
        f"Сезон: {settings.pvp_season}"
    )


async def _health_counts(
    pvp_store: PvPStore,
    moderation_repository: ModerationRepository,
) -> tuple[int, int, int]:
    active = await pvp_store.active_count()
    queued = await pvp_store.queue_count()
    reports = await moderation_repository.open_report_count()
    return active, queued, reports
