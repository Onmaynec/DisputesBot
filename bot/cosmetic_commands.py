from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from .config import Settings
from .cosmetic_repository import CosmeticRepository
from .cosmetics import (
    COSMETIC_CATALOG,
    CosmeticKind,
    EquipStatus,
    PurchaseStatus,
    cosmetics_by_kind,
)
from .pvp_models import PvPUser

router = Router(name="cosmetics")


def _pvp_user(message: Message) -> PvPUser | None:
    if message.from_user is None:
        return None
    return PvPUser(
        user_id=message.from_user.id,
        username=message.from_user.username,
        display_name=message.from_user.full_name,
    )


@router.message(Command("shop"))
async def shop_command(
    message: Message,
    cosmetic_repository: CosmeticRepository,
    settings: Settings,
) -> None:
    if message.from_user is None:
        return
    inventory = await cosmetic_repository.inventory(
        message.from_user.id,
        settings.pvp_season,
    )
    lines = [
        f"🛍 Магазин PvP-косметики — {settings.pvp_season}",
        f"Баланс: {inventory.tokens} 🪙 · {inventory.season_points} ⭐",
        "",
    ]
    section_names = {
        CosmeticKind.BADGE: "Значки",
        CosmeticKind.TITLE: "Титулы",
    }
    for kind in (CosmeticKind.BADGE, CosmeticKind.TITLE):
        lines.append(f"{section_names[kind]}:")
        equipped_id = (
            inventory.equipped_badge_id
            if kind is CosmeticKind.BADGE
            else inventory.equipped_title_id
        )
        for item in cosmetics_by_kind(kind):
            if item.item_id == equipped_id:
                state = "🎖 экипировано"
            elif item.item_id in inventory.owned_item_ids:
                state = "✅ куплено"
            elif inventory.season_points < item.required_points:
                state = f"🔒 нужно {item.required_points} ⭐"
            else:
                state = "🛒 доступно"
            lines.append(
                f"• {item.display} {item.name} (`{item.item_id}`) — "
                f"{item.price_tokens} 🪙 · {state}"
            )
        lines.append("")
    lines.append("Покупка: /buy item_id · экипировка: /equip item_id")
    await message.answer("\n".join(lines), parse_mode="Markdown")


@router.message(Command("buy"))
async def buy_command(
    message: Message,
    command: CommandObject,
    cosmetic_repository: CosmeticRepository,
    settings: Settings,
) -> None:
    user = _pvp_user(message)
    if user is None:
        return
    item_id = (command.args or "").strip().lower()
    if not item_id:
        await message.answer("Укажите предмет: /buy item_id. Каталог: /shop")
        return
    result = await cosmetic_repository.purchase(user, settings.pvp_season, item_id)
    if result.status is PurchaseStatus.UNKNOWN_ITEM:
        await message.answer("Такого предмета нет. Откройте каталог командой /shop.")
        return
    assert result.item is not None
    if result.status is PurchaseStatus.ALREADY_OWNED:
        await message.answer(
            f"{result.item.display} {result.item.name} уже есть в инвентаре."
        )
    elif result.status is PurchaseStatus.LOCKED:
        await message.answer(
            f"🔒 {result.item.name} откроется при {result.item.required_points} ⭐. "
            f"Сейчас: {result.season_points} ⭐."
        )
    elif result.status is PurchaseStatus.INSUFFICIENT_TOKENS:
        missing = max(0, result.item.price_tokens - result.tokens)
        await message.answer(
            f"Недостаточно токенов: нужно ещё {missing} 🪙. "
            "Выполняйте задания через /daily."
        )
    else:
        equipped = "\n🎖 Предмет автоматически экипирован." if result.auto_equipped else ""
        await message.answer(
            f"✅ Куплено: {result.item.display} {result.item.name}\n"
            f"Списано: {result.item.price_tokens} 🪙\n"
            f"Баланс: {result.tokens} 🪙{equipped}"
        )


@router.message(Command("inventory"))
async def inventory_command(
    message: Message,
    cosmetic_repository: CosmeticRepository,
    settings: Settings,
) -> None:
    if message.from_user is None:
        return
    inventory = await cosmetic_repository.inventory(
        message.from_user.id,
        settings.pvp_season,
    )
    if not inventory.owned_item_ids:
        await message.answer(
            "Инвентарь пуст. Получайте токены через /daily и откройте /shop."
        )
        return
    lines = [
        f"🎒 Инвентарь — {settings.pvp_season}",
        f"Баланс: {inventory.tokens} 🪙",
        "",
    ]
    for item in COSMETIC_CATALOG:
        if item.item_id not in inventory.owned_item_ids:
            continue
        equipped = item.item_id in {
            inventory.equipped_title_id,
            inventory.equipped_badge_id,
        }
        suffix = " · экипировано" if equipped else ""
        lines.append(f"• {item.display} {item.name} (`{item.item_id}`){suffix}")
    lines.extend(
        [
            "",
            "Экипировать: /equip item_id",
            "Снять: /unequip title или /unequip badge",
        ]
    )
    await message.answer("\n".join(lines), parse_mode="Markdown")


@router.message(Command("equip"))
async def equip_command(
    message: Message,
    command: CommandObject,
    cosmetic_repository: CosmeticRepository,
    settings: Settings,
) -> None:
    if message.from_user is None:
        return
    item_id = (command.args or "").strip().lower()
    if not item_id:
        await message.answer("Укажите предмет: /equip item_id. Инвентарь: /inventory")
        return
    result = await cosmetic_repository.equip(
        message.from_user.id,
        settings.pvp_season,
        item_id,
    )
    if result.status is EquipStatus.UNKNOWN_ITEM:
        await message.answer("Неизвестный предмет. Откройте /shop.")
    elif result.status is EquipStatus.NOT_OWNED:
        assert result.item is not None
        await message.answer(
            f"Сначала купите {result.item.display} {result.item.name}: "
            f"/buy {result.item.item_id}"
        )
    else:
        assert result.item is not None
        await message.answer(
            f"🎖 Экипировано: {result.item.display} {result.item.name}"
        )


@router.message(Command("unequip"))
async def unequip_command(
    message: Message,
    command: CommandObject,
    cosmetic_repository: CosmeticRepository,
    settings: Settings,
) -> None:
    if message.from_user is None:
        return
    raw_kind = (command.args or "").strip().lower()
    aliases = {
        "title": CosmeticKind.TITLE,
        "титул": CosmeticKind.TITLE,
        "badge": CosmeticKind.BADGE,
        "значок": CosmeticKind.BADGE,
    }
    kind = aliases.get(raw_kind)
    if kind is None:
        await message.answer("Используйте /unequip title или /unequip badge.")
        return
    result = await cosmetic_repository.unequip(
        message.from_user.id,
        settings.pvp_season,
        kind,
    )
    if result.status is EquipStatus.EMPTY_INVENTORY or result.item is None:
        await message.answer("В этом слоте ничего не экипировано.")
    else:
        await message.answer(f"Снято: {result.item.display} {result.item.name}")
