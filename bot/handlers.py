from __future__ import annotations

import random
from collections.abc import Awaitable, Callable

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import CallbackQuery, Message

from .debate_utils import detect_stance
from .keyboards import tournament_topics_keyboard
from .llm import DebateEngine, DebateGenerationError, ROUND_FOCUS
from .models import DebateMode, DebateSession, Stance
from .storage import LeaderboardStore, MemoryStore

router = Router(name=__name__)

ROLES = {"философ", "юрист", "шутник", "циник"}
TOURNAMENT_TOPICS = [
    "Искусственный интеллект должен иметь юридическую ответственность",
    "Социальные сети приносят обществу больше вреда, чем пользы",
    "Высшее образование должно быть бесплатным",
    "Удалённая работа эффективнее офисной",
    "Анонимность в интернете необходимо ограничить",
    "Освоение Марса важнее исследования океана",
    "Четырёхдневная рабочая неделя должна стать стандартом",
    "Школьные оценки нужно отменить",
    "Государство должно вводить безусловный базовый доход",
    "Технологический прогресс делает людей счастливее",
    "Реклама для детей должна быть запрещена",
    "Общественный транспорт в городах должен быть бесплатным",
]

START_TEXT = """⚔️ Добро пожаловать в DisputesBot!

Я всегда занимаю противоположную сторону и помогаю тренировать логику, аргументацию и реакцию на возражения.

Как начать:
1. /debate [тема] — обычный спор.
2. Напишите «за» или «против».
3. Отвечайте на один аргумент за раз.

Команды:
/debate [тема] — начать спор
/role [роль] — философ, юрист, шутник или циник
/summary — резюме тезисов обеих сторон
/judge — выбрать победителя с обоснованием
/tournament — турнир из 3 раундов
/leaderboard — таблица лидеров

Пример: /debate Удалённая работа лучше офисной"""


def _stance_prompt(topic: str) -> str:
    return (
        f"🎯 Тема: {topic}\n\n"
        "Выберите позицию и напишите одним сообщением: «за» или «против». "
        "Я займу противоположную сторону и начну первым аргументом."
    )


def _round_header(session: DebateSession) -> str:
    return (
        f"🏁 Раунд {session.tournament_round}/3\n"
        f"Фокус: {ROUND_FOCUS[session.tournament_round]}"
    )


async def _generate_or_report(
    message: Message,
    operation: Callable[[], Awaitable[str]],
) -> str | None:
    try:
        return await operation()
    except DebateGenerationError:
        await message.answer(
            "⚠️ Не удалось получить ответ от модели. Проверьте OPENAI_API_KEY, "
            "OPENAI_MODEL и доступность API, затем повторите сообщение."
        )
        return None


@router.message(CommandStart())
async def start_command(message: Message) -> None:
    await message.answer(START_TEXT)


@router.message(Command("debate"))
async def debate_command(
    message: Message,
    command: CommandObject,
    store: MemoryStore,
) -> None:
    topic = (command.args or "").strip()
    if not topic:
        await message.answer(
            "Укажите тему после команды.\nПример: /debate Роботы заменят большинство профессий"
        )
        return
    if len(topic) > 300:
        await message.answer("Тема слишком длинная. Сформулируйте её в пределах 300 символов.")
        return
    if message.from_user is None:
        return
    store.create_session(message.from_user.id, topic)
    await message.answer(_stance_prompt(topic))


@router.message(Command("role"))
async def role_command(
    message: Message,
    command: CommandObject,
    store: MemoryStore,
) -> None:
    if message.from_user is None:
        return
    role = (command.args or "").strip().casefold().replace("ё", "е")
    if role not in ROLES:
        await message.answer(
            "🎭 Доступные роли: философ, юрист, шутник, циник.\n"
            "Пример: /role юрист"
        )
        return
    store.set_role(message.from_user.id, role)
    await message.answer(f"🎭 Роль изменена: {role}. Новый стиль применится к следующим аргументам.")


@router.message(Command("summary"))
async def summary_command(
    message: Message,
    store: MemoryStore,
    engine: DebateEngine,
) -> None:
    if message.from_user is None:
        return
    session = store.get_session(message.from_user.id)
    if session is None or len(session.history) < 2:
        await message.answer("Сначала начните спор командой /debate или /tournament.")
        return
    summary = await _generate_or_report(message, lambda: engine.summary(session))
    if summary:
        await message.answer(f"📝 Резюме спора\n\n{summary}")


@router.message(Command("judge"))
async def judge_command(
    message: Message,
    store: MemoryStore,
    engine: DebateEngine,
) -> None:
    if message.from_user is None:
        return
    session = store.get_session(message.from_user.id)
    if session is None or session.user_argument_count == 0:
        await message.answer("Для суда нужен хотя бы один ваш аргумент.")
        return
    verdict = await _generate_or_report(message, lambda: engine.judge(session))
    if verdict:
        await message.answer(f"⚖️ Вердикт\n\n{verdict}")


@router.message(Command("tournament"))
async def tournament_command(message: Message, store: MemoryStore) -> None:
    if message.from_user is None:
        return
    topics = random.sample(TOURNAMENT_TOPICS, k=3)
    store.tournament_choices[message.from_user.id] = topics
    await message.answer(
        "🏆 Турнир дебатов\n\nВыберите одну из трёх случайных тем:",
        reply_markup=tournament_topics_keyboard(topics),
    )


@router.callback_query(F.data.startswith("tournament:"))
async def tournament_topic_callback(
    callback: CallbackQuery,
    store: MemoryStore,
) -> None:
    await callback.answer()
    if callback.message is None:
        return
    topics = store.tournament_choices.get(callback.from_user.id)
    if not topics:
        await callback.message.answer("Выбор устарел. Запустите /tournament ещё раз.")
        return
    try:
        index = int((callback.data or "").split(":", maxsplit=1)[1])
        topic = topics[index]
    except (ValueError, IndexError):
        await callback.message.answer("Не удалось выбрать тему. Запустите /tournament ещё раз.")
        return

    store.tournament_choices.pop(callback.from_user.id, None)
    store.create_session(callback.from_user.id, topic, DebateMode.TOURNAMENT)
    await callback.message.edit_text(f"🏆 Выбрана тема: {topic}")
    await callback.message.answer(
        "Турнир состоит из 3 раундов. В каждом раунде — по 3 аргумента от каждой стороны.\n\n"
        + _stance_prompt(topic)
    )


@router.message(Command("leaderboard"))
async def leaderboard_command(message: Message, leaderboard: LeaderboardStore) -> None:
    entries = await leaderboard.top(10)
    if not entries:
        await message.answer("🏆 Таблица лидеров пока пуста. Завершите первый /tournament!")
        return
    lines = ["🏆 Таблица лидеров", ""]
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    for position, (key, entry) in enumerate(entries, start=1):
        prefix = medals.get(position, f"{position}.")
        lines.append(
            f"{prefix} {key} — лучший результат {entry.get('best_total', 0)}/30, "
            f"средний {entry.get('average_total', 0)}/30, турниров: {entry.get('tournaments', 0)}"
        )
    await message.answer("\n".join(lines))


@router.message(F.text)
async def debate_message(
    message: Message,
    store: MemoryStore,
    engine: DebateEngine,
    leaderboard: LeaderboardStore,
) -> None:
    if message.from_user is None or message.text is None:
        return
    if message.text.startswith("/"):
        await message.answer("Неизвестная команда. Нажмите /start, чтобы увидеть список команд.")
        return

    session = store.get_session(message.from_user.id)
    if session is None:
        await message.answer("Сначала начните спор: /debate [тема] или /tournament.")
        return

    if session.is_waiting_for_stance:
        detected = detect_stance(message.text)
        if detected is None:
            await message.answer("Напишите явно «за» или «против», чтобы я занял другую сторону.")
            return
        session.set_stance(Stance(detected))
        opening = await _generate_or_report(
            message,
            lambda: engine.argument(session, opening=True),
        )
        if opening is None:
            return
        session.add_bot_argument(opening)
        if session.mode is DebateMode.TOURNAMENT:
            await message.answer(
                f"{_round_header(session)}\n\n"
                f"🤖 Аргумент 1/3 ({session.bot_stance.value}):\n{opening}"
            )
        else:
            await message.answer(
                f"🤖 Моя позиция: {session.bot_stance.value}\n\n{opening}\n\nВаш ход."
            )
        return

    session.add_user_argument(message.text)

    if session.mode is DebateMode.TOURNAMENT:
        await _handle_tournament_argument(message, session, store, engine, leaderboard)
        return

    counterargument = await _generate_or_report(
        message,
        lambda: engine.argument(session),
    )
    if counterargument is None:
        return
    session.add_bot_argument(counterargument)
    response_parts = [f"🤖 Контраргумент:\n{counterargument}"]

    if (
        session.user_argument_count % 5 == 0
        and session.last_progress_review_at != session.user_argument_count
    ):
        review = await _generate_or_report(message, lambda: engine.progress_review(session))
        if review:
            session.last_progress_review_at = session.user_argument_count
            response_parts.append(f"📊 Разбор после 5 сообщений:\n{review}")

    response_parts.append("Ваш ход.")
    await message.answer("\n\n".join(response_parts))


async def _handle_tournament_argument(
    message: Message,
    session: DebateSession,
    store: MemoryStore,
    engine: DebateEngine,
    leaderboard: LeaderboardStore,
) -> None:
    response_parts: list[str] = []

    if session.bot_arguments_in_round < 3:
        counterargument = await _generate_or_report(message, lambda: engine.argument(session))
        if counterargument is None:
            return
        session.add_bot_argument(counterargument)
        response_parts.append(
            f"🤖 Аргумент {session.bot_arguments_in_round}/3:\n{counterargument}"
        )

    if (
        session.user_argument_count % 5 == 0
        and session.last_progress_review_at != session.user_argument_count
    ):
        review = await _generate_or_report(message, lambda: engine.progress_review(session))
        if review:
            session.last_progress_review_at = session.user_argument_count
            response_parts.append(f"📊 Промежуточный разбор:\n{review}")

    if session.user_arguments_in_round < 3:
        response_parts.append(
            f"Ваш аргумент: {session.user_arguments_in_round}/3. Продолжайте раунд."
        )
        await message.answer("\n\n".join(response_parts))
        return

    feedback = await _generate_or_report(message, lambda: engine.round_feedback(session))
    if feedback is None:
        return
    response_parts.append(f"🧭 Обратная связь за раунд {session.tournament_round}:\n{feedback}")

    if session.tournament_round < 3:
        session.tournament_round += 1
        session.reset_round_counters()
        opening = await _generate_or_report(message, lambda: engine.argument(session, opening=True))
        if opening is None:
            return
        session.add_bot_argument(opening)
        response_parts.append(
            f"{_round_header(session)}\n\n"
            f"🤖 Аргумент 1/3:\n{opening}"
        )
        await message.answer("\n\n".join(response_parts))
        return

    try:
        scores = await engine.tournament_scores(session)
    except DebateGenerationError:
        await message.answer("⚠️ Не удалось рассчитать финальную оценку. Повторите /judge позже.")
        return

    await leaderboard.record_result(
        user_id=message.from_user.id,
        username=message.from_user.username,
        display_name=message.from_user.full_name,
        scores=scores,
    )
    winner_labels = {"user": "Пользователь", "bot": "Бот", "draw": "Ничья"}
    response_parts.append(
        "🏆 Финальная оценка\n"
        f"Логика: {scores.logic}/10\n"
        f"Аргументация: {scores.argumentation}/10\n"
        f"Креативность: {scores.creativity}/10\n"
        f"Итого: {scores.total}/30\n"
        f"Победитель: {winner_labels[scores.winner]}\n"
        f"Обоснование: {scores.reason}\n\n"
        "Результат сохранён в таблице лидеров: /leaderboard"
    )
    await message.answer("\n\n".join(response_parts))
    store.sessions.pop(message.from_user.id, None)
