from __future__ import annotations

import random

from aiogram import Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import Message

from .achievements import ACHIEVEMENT_BY_ID, ACHIEVEMENTS, level_title
from .config import Settings
from .guard import RequestGuard
from .handlers import TOURNAMENT_TOPICS, _allow_request, _generate_or_report, _stance_prompt
from .keyboards import tournament_topics_keyboard
from .llm import JudgeEngine
from .models import DebateArchiveEntry, DebateMode
from .profile_store import ProfileStore
from .storage import SessionStore
from .v03_engine import V03DebateEngine

router = Router(name="v03")

START_TEXT = """⚔️ Добро пожаловать в DisputesBot v0.3!

Я занимаю противоположную сторону и помогаю тренировать логику,
аргументацию и реакцию на возражения.

Основные команды:
/debate [тема] — начать спор
/role [роль] — философ, юрист, шутник или циник
/difficulty [уровень] — новичок, опытный или эксперт
/summary — резюме тезисов
/judge — независимый судья
/fallacies — анализ логических ошибок
/tournament — турнир из 3 раундов
/history — история сохранённых споров
/rematch — повторить последнюю тему
/stats — расширенная статистика
/achievements — достижения
/leaderboard — таблица лидеров
/cancel — сохранить и завершить спор

Пример: /debate Удалённая работа лучше офисной"""


def _achievement_notice(profile: dict[str, object]) -> str | None:
    raw_ids = profile.get("new_achievements", [])
    ids = raw_ids if isinstance(raw_ids, list) else []
    labels = [
        f"{ACHIEVEMENT_BY_ID[item].emoji} {ACHIEVEMENT_BY_ID[item].title}"
        for item in ids
        if isinstance(item, str) and item in ACHIEVEMENT_BY_ID
    ]
    return "🎉 Новые достижения: " + ", ".join(labels) if labels else None


def _history_label(entry: DebateArchiveEntry) -> str:
    statuses = {
        "judged": "⚖️ оценён",
        "cancelled": "🛑 завершён",
        "completed": "🏆 турнир",
        "replaced": "🔄 заменён",
    }
    winners = {"user": "победа", "bot": "поражение", "draw": "ничья", "none": "—"}
    score = f", {entry.score_total}/30" if entry.score_total is not None else ""
    return (
        f"{entry.ended_at:%d.%m.%Y} · {statuses[entry.status]}\n"
        f"{entry.topic}\n"
        f"Результат: {winners[entry.winner]}{score}; аргументов: "
        f"{entry.user_argument_count}"
    )


async def _archive_existing(
    message: Message,
    store: SessionStore,
    profiles: ProfileStore,
) -> None:
    if message.from_user is None:
        return
    session = await store.get_session(message.from_user.id)
    if session is None or session.user_argument_count == 0:
        return
    await profiles.archive_debate(
        user_id=message.from_user.id,
        username=message.from_user.username,
        display_name=message.from_user.full_name,
        session=session,
        status="replaced",
    )


@router.message(CommandStart())
async def start_command(message: Message) -> None:
    await message.answer(START_TEXT)


@router.message(Command("debate"))
async def debate_command(
    message: Message,
    command: CommandObject,
    store: SessionStore,
    leaderboard: ProfileStore,
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
        await _archive_existing(message, store, leaderboard)
        await store.create_session(message.from_user.id, topic)
    await message.answer(_stance_prompt(topic))


@router.message(Command("tournament"))
async def tournament_command(
    message: Message,
    store: SessionStore,
    leaderboard: ProfileStore,
    guard: RequestGuard,
) -> None:
    if message.from_user is None or not await _allow_request(message, guard):
        return
    topics = random.sample(TOURNAMENT_TOPICS, k=3)
    async with guard.hold(message.from_user.id) as acquired:
        if not acquired:
            await message.answer("⏳ Предыдущий запрос ещё обрабатывается.")
            return
        await _archive_existing(message, store, leaderboard)
        await store.set_tournament_choices(message.from_user.id, topics)
    await message.answer(
        "🏆 Турнир дебатов\n\nВыберите одну из трёх случайных тем:",
        reply_markup=tournament_topics_keyboard(topics),
    )


@router.message(Command("cancel"))
async def cancel_command(
    message: Message,
    store: SessionStore,
    leaderboard: ProfileStore,
    guard: RequestGuard,
) -> None:
    if message.from_user is None:
        return
    profile: dict[str, object] | None = None
    async with guard.hold(message.from_user.id) as acquired:
        if not acquired:
            await message.answer("⏳ Текущий ответ уже формируется. Повторите /cancel после него.")
            return
        session = await store.get_session(message.from_user.id)
        if session and session.user_argument_count:
            profile = await leaderboard.archive_debate(
                user_id=message.from_user.id,
                username=message.from_user.username,
                display_name=message.from_user.full_name,
                session=session,
                status="cancelled",
            )
        await store.delete_session(message.from_user.id)
    if session is None:
        await message.answer("Активного спора нет.")
        return
    text = "🛑 Спор сохранён в истории и завершён. Новый: /debate [тема]"
    notice = _achievement_notice(profile or {})
    await message.answer(text + (f"\n\n{notice}" if notice else ""))


@router.message(Command("judge"))
async def judge_command(
    message: Message,
    store: SessionStore,
    judge_engine: JudgeEngine,
    leaderboard: ProfileStore,
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
        if session.mode is DebateMode.TOURNAMENT:
            await message.answer(
                "В турнире итоговый суд запускается автоматически после 3-го раунда."
            )
            return
        judged = await _generate_or_report(message, lambda: judge_engine.judge(session))
        if judged is None:
            return
        verdict, participant_a = judged
        user_scores = verdict.participant_a if participant_a == "user" else verdict.participant_b
        bot_scores = verdict.participant_b if participant_a == "user" else verdict.participant_a
        winner_labels = {
            "draw": "Ничья",
            "A": "Пользователь" if participant_a == "user" else "Бот",
            "B": "Бот" if participant_a == "user" else "Пользователь",
        }
        winner_label = winner_labels[verdict.winner]
        if winner_label == "Ничья":
            winner = "draw"
        elif winner_label == "Пользователь":
            winner = "user"
        else:
            winner = "bot"
        profile = await leaderboard.archive_debate(
            user_id=message.from_user.id,
            username=message.from_user.username,
            display_name=message.from_user.full_name,
            session=session,
            status="judged",
            winner=winner,
            score_total=user_scores.total,
        )
        await store.save_session(message.from_user.id, session)
    text = (
        "⚖️ Независимый вердикт\n\n"
        f"Победитель: {winner_label}\n\n"
        "Пользователь:\n"
        f"• Логика: {user_scores.logic}/10\n"
        f"• Доказательность: {user_scores.evidence}/10\n"
        f"• Работа с возражениями: {user_scores.rebuttal}/10\n\n"
        "Бот:\n"
        f"• Логика: {bot_scores.logic}/10\n"
        f"• Доказательность: {bot_scores.evidence}/10\n"
        f"• Работа с возражениями: {bot_scores.rebuttal}/10\n\n"
        f"Обоснование: {verdict.reasoning}\n"
        f"Решающая деталь: {verdict.decisive_point}\n\n"
        "Спор сохранён в /history"
    )
    notice = _achievement_notice(profile)
    await message.answer(text + (f"\n\n{notice}" if notice else ""))


@router.message(Command("fallacies"))
async def fallacies_command(
    message: Message,
    store: SessionStore,
    engine: V03DebateEngine,
    leaderboard: ProfileStore,
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
            await message.answer("Сначала приведите хотя бы один аргумент в активном споре.")
            return
        analysis = await _generate_or_report(message, lambda: engine.fallacy_analysis(session))
        if analysis is None:
            return
        names = [item.name for item in analysis.fallacies]
        session.last_fallacies = names[:10]
        await store.save_session(message.from_user.id, session)
        profile = await leaderboard.record_fallacy_analysis(
            user_id=message.from_user.id,
            username=message.from_user.username,
            display_name=message.from_user.full_name,
            names=names,
        )
    if not analysis.fallacies:
        text = (
            "🔎 Формальных логических ошибок не обнаружено.\n\n"
            f"Совет: {analysis.overall_advice}"
        )
    else:
        blocks = []
        for index, item in enumerate(analysis.fallacies, start=1):
            blocks.append(
                f"{index}. {item.name} · уверенность: {item.confidence}\n"
                f"Фрагмент: «{item.excerpt}»\n"
                f"Почему это проблема: {item.explanation}\n"
                f"Как улучшить: {item.improvement}"
            )
        blocks.append(f"Общий совет: {analysis.overall_advice}")
        text = "🔎 Анализ логических ошибок\n\n" + "\n\n".join(blocks)
    notice = _achievement_notice(profile)
    await message.answer(text + (f"\n\n{notice}" if notice else ""))


@router.message(Command("history"))
async def history_command(
    message: Message,
    command: CommandObject,
    leaderboard: ProfileStore,
) -> None:
    if message.from_user is None:
        return
    try:
        limit = int((command.args or "5").strip())
    except ValueError:
        limit = 5
    entries = await leaderboard.history(message.from_user.id, max(1, min(limit, 10)))
    if not entries:
        await message.answer("📚 История пока пуста. Завершите спор через /judge или /cancel.")
        return
    blocks = [f"{index}. {_history_label(item)}" for index, item in enumerate(entries, start=1)]
    await message.answer("📚 Последние споры\n\n" + "\n\n".join(blocks))


@router.message(Command("rematch"))
async def rematch_command(
    message: Message,
    store: SessionStore,
    leaderboard: ProfileStore,
    guard: RequestGuard,
) -> None:
    if message.from_user is None:
        return
    async with guard.hold(message.from_user.id) as acquired:
        if not acquired:
            await message.answer("⏳ Предыдущий запрос ещё обрабатывается.")
            return
        if await store.get_session(message.from_user.id) is not None:
            await message.answer("Сначала завершите активный спор командой /cancel.")
            return
        previous = await leaderboard.last_debate(message.from_user.id)
        if previous is None:
            await message.answer("Нет сохранённого спора для повтора. Начните с /debate [тема].")
            return
        await store.create_session(message.from_user.id, previous.topic, previous.mode)
    mode = "турнир" if previous.mode is DebateMode.TOURNAMENT else "обычный спор"
    await message.answer(f"🔄 Повторный матч · {mode}\n\n{_stance_prompt(previous.topic)}")


@router.message(Command("leaderboard"))
async def leaderboard_command(message: Message, leaderboard: ProfileStore) -> None:
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
            f"{prefix} {label} — {entry.get('best_total', 0)}/30, "
            f"уровень {entry.get('level', 1)}, XP {entry.get('xp', 0)}"
        )
    await message.answer("\n".join(lines))


@router.message(Command("stats"))
async def stats_command(
    message: Message,
    store: SessionStore,
    leaderboard: ProfileStore,
) -> None:
    if message.from_user is None:
        return
    entry = await leaderboard.get_user(message.from_user.id)
    session = await store.get_session(message.from_user.id)
    rank = await leaderboard.rank(message.from_user.id)
    lines = ["📊 Ваша статистика", ""]
    if entry:
        tournaments = int(entry.get("tournaments", 0))
        totals = entry.get("score_totals", {})
        if not isinstance(totals, dict):
            totals = {}
        averages = {
            key: round(float(totals.get(key, 0)) / tournaments, 1) if tournaments else 0
            for key in ("logic", "argumentation", "creativity")
        }
        raw_fallacies = entry.get("fallacy_counts", {})
        fallacy_counts = raw_fallacies if isinstance(raw_fallacies, dict) else {}
        fallacies = sorted(
            fallacy_counts.items(),
            key=lambda item: int(item[1]),
            reverse=True,
        )[:3]
        level = int(entry.get("level", 1))
        achievements = entry.get("achievements", [])
        achievement_count = len(achievements) if isinstance(achievements, list) else 0
        lines.extend(
            [
                f"Уровень: {level} — {level_title(level)}",
                f"Опыт: {entry.get('xp', 0)} XP",
                f"Место в рейтинге: {rank or '—'}",
                f"Сохранённых споров: {entry.get('completed_debates', 0)}",
                f"Турниров: {tournaments}",
                f"Победы / ничьи / поражения: {entry.get('wins', 0)} / "
                f"{entry.get('draws', 0)} / {entry.get('losses', 0)}",
                f"Лучший результат: {entry.get('best_total', 0)}/30",
                f"Средний результат: {entry.get('average_total', 0)}/30",
                f"Средние критерии: логика {averages['logic']}, аргументация "
                f"{averages['argumentation']}, креативность {averages['creativity']}",
                f"Лучшая серия побед: {entry.get('best_streak', 0)}",
                f"Достижения: {achievement_count}/{len(ACHIEVEMENTS)}",
            ]
        )
        if fallacies:
            lines.append(
                "Частые ошибки: " + ", ".join(f"{name} ×{count}" for name, count in fallacies)
            )
    else:
        lines.append("Сохранённой статистики пока нет.")
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


@router.message(Command("achievements"))
async def achievements_command(message: Message, leaderboard: ProfileStore) -> None:
    if message.from_user is None:
        return
    entry = await leaderboard.get_user(message.from_user.id) or {}
    raw = entry.get("achievements", [])
    unlocked = set(raw) if isinstance(raw, list) else set()
    lines = ["🏅 Достижения", ""]
    for item in ACHIEVEMENTS:
        marker = "✅" if item.id in unlocked else "🔒"
        lines.append(f"{marker} {item.emoji} {item.title} — {item.description}")
    await message.answer("\n".join(lines))
