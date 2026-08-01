from __future__ import annotations

import re
from datetime import UTC, datetime

from .models import DebateArchiveEntry, DebateMessage, DebateSession


def _service_text(value: object) -> str:
    text = str(value).replace("\r", " ").replace("\n", " ").strip()
    return text.replace("|", "\\|")


def _quote(text: str) -> str:
    return "\n".join(f"> {line}" if line else ">" for line in text.splitlines())


def _transcript(messages: list[DebateMessage]) -> str:
    blocks: list[str] = []
    for index, item in enumerate(messages, start=1):
        author = "Пользователь" if item.author == "user" else "Бот"
        round_label = f" · раунд {item.round_number}" if item.round_number else ""
        blocks.append(f"### {index}. {author}{round_label}\n\n{_quote(item.text)}")
    return "\n\n".join(blocks) if blocks else "_Сообщений нет._"


def render_session_markdown(session: DebateSession) -> str:
    generated = datetime.now(UTC).isoformat()
    stance = session.user_stance.value if session.user_stance else "не выбрана"
    return (
        "# Экспорт активного спора\n\n"
        f"- **Тема:** {_service_text(session.topic)}\n"
        f"- **Режим:** {_service_text(session.mode.value)}\n"
        f"- **Роль бота:** {_service_text(session.role)}\n"
        f"- **Сложность:** {_service_text(session.difficulty.value)}\n"
        f"- **Позиция пользователя:** {_service_text(stance)}\n"
        f"- **Начат:** {session.started_at.isoformat()}\n"
        f"- **Экспортирован:** {generated}\n\n"
        "## Стенограмма\n\n"
        f"{_transcript(session.history[-80:])}\n"
    )


def render_archive_markdown(entry: DebateArchiveEntry) -> str:
    stance = entry.user_stance.value if entry.user_stance else "не выбрана"
    score = str(entry.score_total) if entry.score_total is not None else "нет"
    fallacies = ", ".join(entry.fallacies) if entry.fallacies else "не зафиксированы"
    return (
        "# Экспорт завершённого спора\n\n"
        f"- **Тема:** {_service_text(entry.topic)}\n"
        f"- **Режим:** {_service_text(entry.mode.value)}\n"
        f"- **Статус:** {_service_text(entry.status)}\n"
        f"- **Победитель:** {_service_text(entry.winner)}\n"
        f"- **Баллы:** {_service_text(score)}\n"
        f"- **Роль бота:** {_service_text(entry.role)}\n"
        f"- **Сложность:** {_service_text(entry.difficulty.value)}\n"
        f"- **Позиция пользователя:** {_service_text(stance)}\n"
        f"- **Начат:** {entry.started_at.isoformat()}\n"
        f"- **Завершён:** {entry.ended_at.isoformat()}\n"
        f"- **Логические ошибки:** {_service_text(fallacies)}\n\n"
        "## Стенограмма\n\n"
        f"{_transcript(entry.transcript[-80:])}\n"
    )


def export_filename(topic: str, *, prefix: str = "debate") -> str:
    normalized = re.sub(r"[^\w-]+", "_", topic, flags=re.UNICODE).strip("_")
    safe_topic = normalized[:48] or "export"
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{safe_topic}_{stamp}.md"
