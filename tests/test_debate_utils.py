from bot.debate_utils import detect_stance


def test_detect_stance() -> None:
    assert detect_stance("Я за эту идею") == "за"
    assert detect_stance("Я не согласен и выступаю против") == "против"
    assert detect_stance("Нужно подумать") is None
