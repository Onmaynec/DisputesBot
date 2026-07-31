from bot.debate_utils import detect_stance
from bot.models import DebateMode, DebateSession, Stance


def test_detect_stance() -> None:
    assert detect_stance("Я за эту идею") == "за"
    assert detect_stance("Против, потому что это дорого") == "против"
    assert detect_stance("Не согласен с тезисом") == "против"
    assert detect_stance("Нужно сначала определить термины") is None


def test_session_tracks_tournament_round() -> None:
    session = DebateSession(topic="Тема", role="юрист", mode=DebateMode.TOURNAMENT)
    session.set_stance(Stance.PRO)
    session.add_bot_argument("Первый аргумент")
    session.add_user_argument("Ответ")

    assert session.bot_stance is Stance.CON
    assert session.bot_arguments_in_round == 1
    assert session.user_arguments_in_round == 1
    assert session.user_argument_count == 1
    assert session.history[-1].round_number == 1
