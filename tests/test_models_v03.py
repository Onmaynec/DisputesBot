from bot.models import DebateArchiveEntry, DebateSession


def test_v02_session_json_gets_v03_defaults() -> None:
    raw = '{"topic":"Тема","role":"философ","history":[],"user_argument_count":0}'
    session = DebateSession.model_validate_json(raw)

    assert session.session_id
    assert session.archive_id is None
    assert session.last_fallacies == []


def test_archive_uses_stable_session_id() -> None:
    session = DebateSession(topic="Тема", role="философ")
    first = DebateArchiveEntry.from_session(session, status="cancelled")
    second = DebateArchiveEntry.from_session(session, status="judged", winner="draw")

    assert first.id == second.id == session.session_id
