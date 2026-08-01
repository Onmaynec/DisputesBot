from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from .config import Settings
from .progression_models import season_tier
from .pvp_models import PvPUser
from .social_models import ProfileLookupStatus, ProfileVisibility, SocialProfileCard
from .social_repository import SocialRepository

router = Router(name="social")


def _pvp_user(message: Message) -> PvPUser | None:
    if message.from_user is None:
        return None
    return PvPUser(
        user_id=message.from_user.id,
        username=message.from_user.username,
        display_name=message.from_user.full_name,
    )


def _target_id(message: Message, command: CommandObject) -> int | None:
    if message.reply_to_message is not None and message.reply_to_message.from_user is not None:
        return message.reply_to_message.from_user.id
    raw = (command.args or "").strip()
    if raw.isdigit() and int(raw) > 0:
        return int(raw)
    return None


def _short_topic(topic: str, limit: int = 72) -> str:
    normalized = " ".join(topic.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip() + "…"


def _render_profile(card: SocialProfileCard, *, own: bool) -> str:
    tier = season_tier(card.season_points)
    badge = f"{card.badge.display} " if card.badge is not None else ""
    title = f" — {card.title.display}" if card.title is not None else ""
    rating = str(card.rating) if card.rating is not None else "нет матчей"
    rank = f"#{card.rank}" if card.rank is not None else "—"
    lines = [
        f"{badge}⚔️ {card.display_name}{title}",
        f"Сезон: {card.season}",
        "",
        f"Elo: {rating} · место: {rank}",
        f"Матчи: {card.games} · победы/ничьи/поражения: "
        f"{card.wins}/{card.draws}/{card.losses}",
        f"Уровень: {tier.number} — {tier.name}",
        f"⭐ Очки сезона: {card.season_points}",
    ]
    if own:
        visibility = "публичный" if card.is_public else "приватный"
        lines.extend(
            [
                f"🪙 Токены: {card.tokens}",
                f"🔐 Профиль: {visibility}",
                "",
                "Видимость: /profile_visibility public или private",
            ]
        )
    else:
        lines.extend(["", f"ID игрока: {card.user_id}"])
    return "\n".join(lines)


@router.message(Command("profile_visibility"))
async def profile_visibility_command(
    message: Message,
    command: CommandObject,
    social_repository: SocialRepository,
) -> None:
    user = _pvp_user(message)
    if user is None:
        return
    raw = (command.args or "").strip().casefold()
    aliases = {
        "public": ProfileVisibility.PUBLIC,
        "публичный": ProfileVisibility.PUBLIC,
        "open": ProfileVisibility.PUBLIC,
        "private": ProfileVisibility.PRIVATE,
        "приватный": ProfileVisibility.PRIVATE,
        "closed": ProfileVisibility.PRIVATE,
    }
    if not raw:
        visibility = await social_repository.visibility(user.user_id)
        label = "публичный" if visibility is ProfileVisibility.PUBLIC else "приватный"
        await message.answer(
            f"🔐 Ваш PvP-профиль: {label}.\n"
            "Изменить: /profile_visibility public или /profile_visibility private"
        )
        return
    visibility = aliases.get(raw)
    if visibility is None:
        await message.answer(
            "Используйте /profile_visibility public или /profile_visibility private."
        )
        return
    await social_repository.set_visibility(user, visibility)
    if visibility is ProfileVisibility.PUBLIC:
        await message.answer(
            "🌐 PvP-профиль стал публичным. Другие игроки смогут открыть его "
            "через /pvp_profile ваш_id. Блок-лист продолжает действовать."
        )
    else:
        await message.answer(
            "🔒 PvP-профиль скрыт. Ваша собственная карточка остаётся доступна вам."
        )


@router.message(Command("pvp_profile"))
async def pvp_profile_command(
    message: Message,
    command: CommandObject,
    social_repository: SocialRepository,
    settings: Settings,
) -> None:
    user = _pvp_user(message)
    if user is None:
        return
    target_id = _target_id(message, command) or user.user_id
    result = await social_repository.profile(user, target_id, settings.pvp_season)
    if result.status is ProfileLookupStatus.NOT_FOUND:
        await message.answer("PvP-профиль не найден.")
        return
    if result.status is ProfileLookupStatus.PRIVATE:
        await message.answer("🔒 Игрок закрыл публичный PvP-профиль.")
        return
    if result.status is ProfileLookupStatus.BLOCKED:
        await message.answer("🚫 Профиль недоступен из-за PvP-блокировки.")
        return
    if result.profile is None:
        return
    await message.answer(
        _render_profile(result.profile, own=target_id == user.user_id)
    )


@router.message(Command("rivals"))
async def rivals_command(
    message: Message,
    social_repository: SocialRepository,
    settings: Settings,
) -> None:
    if message.from_user is None:
        return
    rivals = await social_repository.rivals(
        message.from_user.id,
        settings.pvp_season,
        limit=5,
    )
    if not rivals:
        await message.answer("Соперников пока нет. Найдите матч через /queue.")
        return
    lines = [f"⚔️ Главные соперники — {settings.pvp_season}", ""]
    for index, rival in enumerate(rivals, start=1):
        lines.append(
            f"{index}. {rival.display_name} · ID {rival.opponent_id}\n"
            f"   Матчи {rival.matches} · В/Н/П {rival.wins}/{rival.draws}/{rival.losses} · "
            f"Elo {rival.rating_delta:+d}"
        )
    lines.extend(
        [
            "",
            "Подробно: /head_to_head user_id",
            "Публичная карточка: /pvp_profile user_id",
        ]
    )
    await message.answer("\n".join(lines))


@router.message(Command("head_to_head"))
async def head_to_head_command(
    message: Message,
    command: CommandObject,
    social_repository: SocialRepository,
    settings: Settings,
) -> None:
    if message.from_user is None:
        return
    opponent_id = _target_id(message, command)
    if opponent_id is None:
        await message.answer(
            "Ответьте на сообщение соперника или укажите ID: /head_to_head 123456789"
        )
        return
    if opponent_id == message.from_user.id:
        await message.answer("Нельзя сравнить игрока с самим собой.")
        return
    view = await social_repository.head_to_head(
        message.from_user.id,
        opponent_id,
        settings.pvp_season,
    )
    if view is None:
        await message.answer("Совместных PvP-матчей в текущем сезоне не найдено.")
        return
    lines = [
        f"🥊 Личные встречи с {view.display_name}",
        f"Сезон: {view.season} · ID {view.opponent_id}",
        "",
        f"Матчи: {view.matches} ({view.rated_matches} рейтинговых)",
        f"Победы / ничьи / поражения: {view.wins} / {view.draws} / {view.losses}",
        f"Изменение Elo: {view.rating_delta:+d}",
        f"Текущая серия побед: {view.current_win_streak}",
        f"Последняя встреча: {view.last_played_at.date().isoformat()}",
    ]
    if view.recent_topics:
        lines.extend(["", "Последние темы:"])
        lines.extend(f"• {_short_topic(topic)}" for topic in view.recent_topics)
    await message.answer("\n".join(lines))
