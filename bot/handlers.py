from __future__ import annotations

import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import CallbackQuery, Message

from .config import Settings
from .debate_utils import detect_stance
from .guard import RequestGuard
from .keyboards import tournament_topics_keyboard
from .llm import DebateEngine, DebateGenerationError, JudgeEngine, ROUND_FOCUS
from .models import DebateMode, DebateSession, Difficulty, Stance
from .schemas import ProgressReviewOutput, RoundFeedbackOutput, SummaryOutput
from .storage import LeaderboardStore, SessionStore

router = Router(name=__name__)
ResultT = TypeVar("ResultT")

ROLES = {"философ", "юрист", "шутник", "циник"}
DIFFICULTIES = {item.value: item for item in Difficulty}
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

START_TEXT = """⚔️ Добро пожаловать в DisputesBot v0.2!

Я всегда занимаю противоположную сторону и помогаю тренировать логику, аргументацию и реакцию на возражения.

Как начать:
1. /debate [тема] — обычный спор.
2. Напишите «за» или «против».
3. Отвечайте на один аргумент за раз.

Команды:
/debate [тема] — начать спор
/role [роль] — философ, юрист, шутник или циник
/difficulty [уровень] — новичок, опытный или эксперт
/summary — резюме тезисов обеих сторон
/judge — независимый анонимный судья
/tournament — турнир из 3 раундов
/leaderboard — таблица лидеров
/stats — личная статистика
/cancel — завершить активный спор

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
    operation: Callable[[], Awaitable[ResultT]],
) -> ResultT | None:
    try:
        return await operation()
    except DebateGenerationError:
        await message.answer(
            "⚠️ Не удалось получить корректный ответ модели. Попробуйте повторить ход позже."
        )
        return None


async def _allow_request(message: Message, guard: RequestGuard) -> bool:
    if message.from_user is None:
        return False
    retry_after = await guard.retry_after(message.from_user.id)
    if retry_after:
        await message.answer(
            f"⏱ Слишком много запросов. Повторите примерно через {retry_after} сек."
        )
        return False
    return True


def _format_review(review: ProgressReviewOutput) -> str:
    strong = "; ".join(review.strong_points)
    weak = "; ".join(review.weak_points)
    return (
        f"Ваши сильные стороны: {strong}\n"
        f"Слабые места: {weak}\n"
        f"Следующий лучший ход: {review.next_move}"
    )


def _format_summary(summary: SummaryOutput) -> str:
    def bullets(items: list[str]) -> str:
        return "\n".join(f"• {item}" for item in items) if items else "• Не выявлено"

    return (
        f"Тезисы пользователя:\n{bullets(summary.user_theses)}\n\n"
        f"Тезисы бота:\n{bullets(summary.bot_theses)}\n\n"
        f"Точки согласия:\n{bullets(summary.agreements)}\n\n"
        f"Главное расхождение: {summary.main_disagreement}"
    )


def _format_feedback(feedback: RoundFeedbackOutput) -> str:
    return (
        f"Сильный ход: {feedback.strong_move}\n"
        f"Что ослабило позицию: {feedback.weakness}\n"
        f"Как улучшить следующий раунд: {feedback.next_round_advice}"
    )


@router.message(CommandStart())
async def start_command(message: Message) -> None:
    await message.answer(START_TEXT)


@router.message(Command("debate"))
async def debate_command(
    message: Message,
    command: CommandObject,
    store: SessionStore,
    guard: RequestGuard,
    settings: Settings,
) -> None:
    if message.from_user is None or not await _allow_request(message, guard):
        return
    topic = (command.args or "").strip()
    if not topic:
        await message.answer(
            "Укажите тему после команды.\nПример: /debate Роботы заменят большинство профессий"
        )
        return
    if len(topic) > settings.max_topic_chars:
        await message.answer(
            f"Тема слишком длинная. Лимит: {settings.max_topic_chars} символов."
        )
        return
    async with guard.hold(message.from_user.id) as acquired:
        if not acquired:
            await message.answer("⏳ Предыдущий запрос ещё обрабатывается.")
            return
        await store.create_session(message.from_user.id, topic)
    await message.answer(_stance_prompt(topic))


@router.message(Command("role"))
async def role_command(
    message: Message,
    command: CommandObject,
    store: SessionStore,
    guard: RequestGuard,
) -> None:
    if message.from_user is None:
        return
    role = (command.args or "").strip().casefold().replace("ё", "е")
    if role not in ROLES:
        await message.answer(
            "🎭 Доступные роли: философ, юрист, шутник, циник.\nПример: /role юрист"
        )
        return
    async with guard.hold(message.from_user.id) as acquired:
        if not acquired:
            await message.answer("⏳ Предыдущий запрос ещё обрабатывается.")
            return
        await store.set_role(message.from_user.id, role)
    await message.answer(f"🎭 Роль изменена: {role}. Новый стиль применится сразу.")


@router.message(Command("difficulty"))
async def difficulty_command(
    message: Message,
    command: CommandObject,
    store: SessionStore,
    guard: RequestGuard,
) -> None:
    if message.from_user is None:
        return
    value = (command.args or "").strip().casefold().replace("ё", "е")
    difficulty = DIFFICULTIES.get(value)
    if difficulty is None:
        await message.answer(
            "🎚 Уровни: новичок, опытный, эксперт.\nПример: /difficulty эксперт"
        )
        return
    async with guard.hold(message.from_user.id) as acquired:
        if not acquired:
            await message.answer("⏳ Предыдущий запрос ещё обрабатывается.")
            return
        await store.set_difficulty(message.from_user.id, difficulty)
    await message.answer(f"🎚 Сложность изменена: {difficulty.value}.")


@router.message(Command("cancel"))
async def cancel_command(
    message: Message,
    store: SessionStore,
    guard: RequestGuard,
) -> None:
    if message.from_user is None:
        return
    async with guard.hold(message.from_user.id) as acquired:
        if not acquired:
            await message.answer("⏳ Текущий ответ уже формируется. Повторите /cancel после него.")
            return
        session = await store.get_session(message.from_user.id)
        await store.delete_session(message.from_user.id)
    if session:
        await message.answer("🛑 Активный спор завершён. Начать новый: /debate [тема]")
    else:
        await message.answer("Активного спора нет.")


@router.message(Command("summary"))
async def summary_command(
    message: Message,
    store: SessionStore,
    engine: DebateEngine,
    guard: RequestGuard,
) -> None:
    if message.from_user is None or not await _allow_request(message, guard):
        return
    async with guard.hold(message.from_user.id) as acquired:
        if not acquired:
            await message.answer("⏳ Предыдущий запрос ещё обрабатывается.")
            return
        session = await store.get_session(message.from_user.id)
        if session is None or len(session.history) < 2:
            await message.answer("Сначала начните спор командой /debate или /tournament.")
            return
        summary = await _generate_or_report(message, lambda: engine.summary(session))
    if summary:
        await message.answer(f"📝 Резюме спора\n\n{_format_summary(summary)}")


@router.message(Command("judge"))
async def judge_command(
    message: Message,
    store: SessionStore,
    judge_engine: JudgeEngine,
    guard: RequestGuard,
) -> None:
    if message.from_user is None or not await _allow_request(message, guard):
        return
    async with guard.hold(message.from_user.id) as acquired:
        if not acquired:
            await message.answer("⏳ Предыдущий запрос ещё обрабатывается.")
            return
        session = await store.get_session(message.from_user.id)
        if session is None or session.user_argument_count == 0:
            await message.answer("Для суда нужен хотя бы один ваш аргумент.")
            return
        judged = await _generate_or_report(message, lambda: judge_engine.judge(session))
    if judged is None:
        return
    verdict, participant_a = judged
    user_scores = verdict.participant_a if participant_a == "user" else verdict.participant_b
    bot_scores = verdict.participant_b if participant_a == "user" else verdict.participant_a
    winner_map = {
        "draw": "Ничья",
        "A": "Пользователь" if participant_a == "user" else "Бот",
        "B": "Бот" if participant_a == "user" else "Пользователь",
    }
    await message.answer(
        "⚖️ Независимый вердикт\n\n"
        f"Победитель: {winner_map[verdict.winner]}\n\n"
        "Пользователь:\n"
        f"• Логика: {user_scores.logic}/10\n"
        f"• Доказательность: {user_scores.evidence}/10\n"
        f"• Работа с возражениями: {user_scores.rebuttal}/10\n\n"
        "Бот:\n"
        f"• Логика: {bot_scores.logic}/10\n"
        f"• Доказательность: {bot_scores.evidence}/10\n"
        f"• Работа с возражениями: {bot_scores.rebuttal}/10\n\n"
        f"Обоснование: {verdict.reasoning}\n"
        f"Решающая деталь: {verdict.decisive_point}"
    )


@router.message(Command("tournament"))
async def tournament_command(
    message: Message,
    store: SessionStore,
    guard: RequestGuard,
) -> None:
    if message.from_user is None or not await _allow_request(message, guard):
        return
    topics = random.sample(TOURNAMENT_TOPICS, k=3)
    async with guard.hold(message.from_user.id) as acquired:
        if not acquired:
            await message.answer("⏳ Предыдущий запрос ещё обрабатывается.")
            return
        await store.set_tournament_choices(message.from_user.id, topics)
    await message.answer(
        "🏆 Турнир дебатов\n\nВыберите одну из трёх случайных тем:",
        reply_markup=tournament_topics_keyboard(topics),
    )


@router.callback_query(F.data.startswith("tournament:"))
async def tournament_topic_callback(
    callback: CallbackQuery,
    store: SessionStore,
    guard: RequestGuard,
) -> None:
    await callback.answer()
    if callback.message is None:
        return
    async with guard.hold(callback.from_user.id) as acquired:
        if not acquired:
            await callback.message.answer("⏳ Предыдущий запрос ещё обрабатывается.")
            return
        topics = await store.pop_tournament_choices(callback.from_user.id)
        if not topics:
            await callback.message.answer("Выбор устарел. Запустите /tournament ещё раз.")
            return
        try:
            index = int((callback.data or "").split(":", maxsplit=1)[1])
            topic = topics[index]
        except (ValueError, IndexError):
            await callback.message.answer("Не удалось выбрать тему. Запустите /tournament ещё раз.")
            return
        await store.create_session(callback.from_user.id, topic, DebateMode.TOURNAMENT)
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
    for position, (_, entry) in enumerate(entries, start=1):
        prefix = medals.get(position, f"{position}.")
        username = entry.get("username")
        label = f"@{username}" if username else entry.get("display_name", "Пользователь")
        lines.append(
            f"{prefix} {label} — лучший {entry.get('best_total', 0)}/30, "
            f"средний {entry.get('average_total', 0)}/30, турниров: "
            f"{entry.get('tournaments', 0)}"
        )
    await message.answer("\n".join(lines))


@router.message(Command("stats"))
async def stats_command(
    message: Message,
    store: SessionStore,
    leaderboard: LeaderboardStore,
) -> None:
    if message.from_user is None:
        return
    entry = await leaderboard.get_user(message.from_user.id)
    session = await store.get_session(message.from_user.id)
    lines = ["📊 Ваша статистика", ""]
    if entry:
        lines.extend(
            [
                f"Турниров: {entry.get('tournaments', 0)}",
                f"Победы / ничьи / поражения: {entry.get('wins', 0)} / "
                f"{entry.get('draws', 0)} / {entry.get('losses', 0)}",
                f"Лучший результат: {entry.get('best_total', 0)}/30",
                f"Средний результат: {entry.get('average_total', 0)}/30",
            ]
        )
    else:
        lines.append("Завершённых турниров пока нет.")
    if session:
        lines.extend(
            [
                "",
                f"Активная тема: {session.topic}",
                f"Роль: {session.role}",
                f"Сложность: {session.difficulty.value}",
                f"Ваших аргументов: {session.user_argument_count}",
            ]
        )
    await message.answer("\n".join(lines))


@router.message(F.text)
async def debate_message(
    message: Message,
    store: SessionStore,
    engine: DebateEngine,
    judge_engine: JudgeEngine,
    leaderboard: LeaderboardStore,
    guard: RequestGuard,
    settings: Settings,
) -> None:
    if message.from_user is None or message.text is None:
        return
    if message.text.startswith("/"):
        await message.answer("Неизвестная команда. Нажмите /start, чтобы увидеть список команд.")
        return
    if len(message.text) > settings.max_argument_chars:
        await message.answer(
            f"Сообщение слишком длинное. Лимит: {settings.max_argument_chars} символов."
        )
        return
    if not await _allow_request(message, guard):
        return

    async with guard.hold(message.from_user.id) as acquired:
        if not acquired:
            await message.answer("⏳ Предыдущий запрос ещё обрабатывается. Дождитесь ответа.")
            return
        session = await store.get_session(message.from_user.id)
        if session is None:
            await message.answer("Сначала начните спор: /debate [тема] или /tournament.")
            return

        if session.is_waiting_for_stance:
            await _handle_stance(message, session, store, engine)
            return

        if session.mode is DebateMode.TOURNAMENT and session.awaiting_final_score:
            await _finish_tournament(
                message, session, store, judge_engine, leaderboard, response_parts=[]
            )
            return

        session.add_user_argument(message.text)
        if session.mode is DebateMode.TOURNAMENT:
            await _handle_tournament_argument(
                message,
                session,
                store,
                engine,
                judge_engine,
                leaderboard,
            )
            return
        await _handle_regular_argument(message, session, store, engine)


async def _handle_stance(
    message: Message,
    session: DebateSession,
    store: SessionStore,
    engine: DebateEngine,
) -> None:
    detected = detect_stance(message.text or "")
    if detected is None:
        await message.answer("Напишите явно «за» или «против», чтобы я занял другую сторону.")
        return
    session.set_stance(Stance(detected))
    opening = await _generate_or_report(message, lambda: engine.argument(session, opening=True))
    if opening is None or message.from_user is None:
        return
    session.add_bot_argument(opening)
    await store.save_session(message.from_user.id, session)
    if session.mode is DebateMode.TOURNAMENT:
        await message.answer(
            f"{_round_header(session)}\n\n"
            f"🤖 Аргумент 1/3 ({session.bot_stance.value}):\n{opening}"
        )
    else:
        await message.answer(
            f"🤖 Моя позиция: {session.bot_stance.value}\n\n{opening}\n\nВаш ход."
        )


async def _handle_regular_argument(
    message: Message,
    session: DebateSession,
    store: SessionStore,
    engine: DebateEngine,
) -> None:
    counterargument = await _generate_or_report(message, lambda: engine.argument(session))
    if counterargument is None or message.from_user is None:
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
            response_parts.append(f"📊 Разбор после 5 сообщений:\n{_format_review(review)}")

    await store.save_session(message.from_user.id, session)
    response_parts.append("Ваш ход.")
    await message.answer("\n\n".join(response_parts))


async def _handle_tournament_argument(
    message: Message,
    session: DebateSession,
    store: SessionStore,
    engine: DebateEngine,
    judge_engine: JudgeEngine,
    leaderboard: LeaderboardStore,
) -> None:
    if message.from_user is None:
        return
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
            response_parts.append(f"📊 Промежуточный разбор:\n{_format_review(review)}")

    if session.user_arguments_in_round < 3:
        await store.save_session(message.from_user.id, session)
        response_parts.append(
            f"Ваш аргумент: {session.user_arguments_in_round}/3. Продолжайте раунд."
        )
        await message.answer("\n\n".join(response_parts))
        return

    feedback = await _generate_or_report(message, lambda: engine.round_feedback(session))
    if feedback is None:
        return
    response_parts.append(
        f"🧭 Обратная связь за раунд {session.tournament_round}:\n{_format_feedback(feedback)}"
    )

    if session.tournament_round < 3:
        session.tournament_round += 1
        session.reset_round_counters()
        opening = await _generate_or_report(message, lambda: engine.argument(session, opening=True))
        if opening is None:
            return
        session.add_bot_argument(opening)
        await store.save_session(message.from_user.id, session)
        response_parts.append(
            f"{_round_header(session)}\n\n🤖 Аргумент 1/3:\n{opening}"
        )
        await message.answer("\n\n".join(response_parts))
        return

    session.awaiting_final_score = True
    await store.save_session(message.from_user.id, session)
    await _finish_tournament(
        message, session, store, judge_engine, leaderboard, response_parts=response_parts
    )


async def _finish_tournament(
    message: Message,
    session: DebateSession,
    store: SessionStore,
    judge_engine: JudgeEngine,
    leaderboard: LeaderboardStore,
    *,
    response_parts: list[str],
) -> None:
    if message.from_user is None:
        return
    scores = await _generate_or_report(message, lambda: judge_engine.tournament_scores(session))
    if scores is None:
        await message.answer(
            "Финальный раунд сохранён. Отправьте любое сообщение, чтобы повторить оценку."
        )
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
        "Результат сохранён: /leaderboard · личная статистика: /stats"
    )
    await message.answer("\n\n".join(response_parts))
    await store.delete_session(message.from_user.id)
