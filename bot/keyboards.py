from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def tournament_topics_keyboard(topics: list[str]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"{index + 1}. {topic}",
                callback_data=f"tournament:{index}",
            )
        ]
        for index, topic in enumerate(topics)
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
