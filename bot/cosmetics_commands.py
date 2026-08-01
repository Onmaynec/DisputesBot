from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from .config import Settings
from .cosmetics_models import EquipOutcome, PurchaseOutcome
from .cosmetics_repository import CosmeticsRepository
from .pvp_models import PvPUser

router = Router(name="cosmetics")


@router.message(Command("shop"))
async def shop_command(
    message: Message,
    cosmetics_repository: CosmeticsRepository,
    settings: Settings,
) -> None:
    if message.from_user is None:
        return
    view = await cosmetics_repository.shop(message.from_user.id, settings.pvp_season)
    lines = [
        f"🛍 Магазин PvP-титулов — {view.season}",
        f"Баланс: {view.tokens} 🪙 · прогресс: {view.season_points} ⭐",
        "",
    ]
    for entry in view.entries:
        item = entry.definition
        if entry.equipped:
            icon = "🟢"
            status = "экипирован"
        elif entry.owned:
            icon = "✅"
            status = "куплен"
        elif not entry.unlocked:
            icon = "🔒"
            status = f"нужно {item.minimum_points} ⭐"
        else:
            icon = "🛒"
            status = f"{item.price_tokens} 🪙"
        lines.append(
            f"{icon} {item.label} [{item.title_id}]\n"
            f"   {item.description} · {status}"
        )
    lines.extend(
        [
            "",
            "Покупка: /buy title_id",
            "Выбор: /equip title_id",
        ]
    )
    await message.answer("\n".join(lines))


@router.message(Command("buy"))
async def buy_command(
    message: Message,
    command: CommandObject,
    cosmetics_repository: CosmeticsRepository,
    settings: Settings,
) -> None:
    if message.from_user is None:
        return
    title_id = (command.args or "").strip()
    if not title_id:
        await message.answer("Укажите ID титула: /buy first_word\nКаталог: /shop")
        return
    result = await cosmetics_repository.purchase(
        PvPUser(
            user_id=message.from_user.id,
            username=message.from_user.username,
            display_name=message.from_user.full_name,
        ),
        settings.pvp_season,
        title_id,
    )
    if result.outcome == PurchaseOutcome.UNKNOWN_TITLE:
        await message.answer("Такого титула нет. Откройте каталог командой /shop.")
        return
    item = result.definition
    if item is None:
        return
    if result.outcome == PurchaseOutcome.ALREADY_OWNED:
        await message.answer(
            f"✅ {item.label} уже находится в вашем инвентаре.\n"
            f"Экипировать: /equip {item.title_id}"
        )
        return
    if result.outcome == PurchaseOutcome.LOCKED:
        await message.answer(
            f"🔒 {item.label} откроется при {item.minimum_points} очках сезона.\n"
            f"Сейчас: {result.season_points} ⭐"
        )
        return
    if result.outcome == PurchaseOutcome.INSUFFICIENT_TOKENS:
        missing = item.price_tokens - result.tokens
        await message.answer(
            f"Недостаточно токенов для {item.label}.\n"
            f"Цена: {item.price_tokens} 🪙 · баланс: {result.tokens} 🪙 · "
            f"не хватает: {missing} 🪙"
        )
        return
    auto = "\nТитул автоматически экипирован." if result.auto_equipped else ""
    await message.answer(
        f"🎉 Куплен титул {item.label}!\n"
        f"Списано: {item.price_tokens} 🪙\n"
        f"Осталось: {result.tokens} 🪙{auto}"
    )


@router.message(Command("inventory"))
async def inventory_command(
    message: Message,
    cosmetics_repository: CosmeticsRepository,
    settings: Settings,
) -> None:
    if message.from_user is None:
        return
    view = await cosmetics_repository.inventory(message.from_user.id, settings.pvp_season)
    equipped = view.equipped.label if view.equipped is not None else "не выбран"
    lines = [
        f"🎒 Инвентарь титулов — {view.season}",
        f"Экипирован: {equipped}",
        f"Баланс: {view.tokens} 🪙",
        "",
    ]
    if not view.owned:
        lines.append("Титулов пока нет. Откройте /shop и выполните /daily.")
    else:
        for item in view.owned:
            marker = "🟢" if view.equipped == item else "▫️"
            lines.append(f"{marker} {item.label} [{item.title_id}]")
        lines.extend(["", "Выбор: /equip title_id", "Снять: /equip none"])
    await message.answer("\n".join(lines))


@router.message(Command("equip"))
async def equip_command(
    message: Message,
    command: CommandObject,
    cosmetics_repository: CosmeticsRepository,
    settings: Settings,
) -> None:
    if message.from_user is None:
        return
    title_id = (command.args or "").strip()
    if not title_id:
        await message.answer(
            "Укажите ID купленного титула: /equip first_word\n"
            "Снять титул: /equip none"
        )
        return
    result = await cosmetics_repository.equip(
        message.from_user.id,
        settings.pvp_season,
        title_id,
    )
    if result.outcome == EquipOutcome.UNKNOWN_TITLE:
        await message.answer("Такого титула нет. Каталог: /shop")
    elif result.outcome == EquipOutcome.NOT_OWNED:
        await message.answer("Сначала купите этот титул через /buy. Инвентарь: /inventory")
    elif result.outcome == EquipOutcome.ALREADY_EQUIPPED:
        await message.answer(f"🟢 {result.definition.label} уже экипирован.")
    elif result.outcome == EquipOutcome.CLEARED:
        await message.answer("Титул снят.")
    elif result.definition is not None:
        await message.answer(f"🟢 Экипирован титул {result.definition.label}.")
