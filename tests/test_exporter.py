from bot.exporter import export_filename, render_archive_markdown, render_session_markdown
from bot.models import DebateArchiveEntry, DebateSession, Stance


def test_active_export_contains_transcript_and_preserves_user_text() -> None:
    session = DebateSession(topic="Удалённая работа | офис", role="юрист")
    session.set_stance(Stance.PRO)
    session.add_user_argument("Первая строка\nВторая строка")
    session.add_bot_argument("Контраргумент")

    result = render_session_markdown(session)

    assert "Экспорт активного спора" in result
    assert "Первая строка" in result
    assert "> Вторая строка" in result
    assert "Удалённая работа \\| офис" in result


def test_archive_export_contains_result() -> None:
    session = DebateSession(topic="Тема", role="философ")
    session.set_stance(Stance.CON)
    archive = DebateArchiveEntry.from_session(
        session,
        status="judged",
        winner="user",
        score_total=24,
    )

    result = render_archive_markdown(archive)

    assert "**Победитель:** user" in result
    assert "**Баллы:** 24" in result


def test_export_filename_is_safe() -> None:
    filename = export_filename("../../Опасная тема?!")
    assert filename.endswith(".md")
    assert ".." not in filename
    assert "/" not in filename
