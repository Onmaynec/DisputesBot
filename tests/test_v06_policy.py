from bot.pvp_repository import PvPRepository


def test_pair_key_is_side_independent() -> None:
    assert PvPRepository.pair_key(10, 2) == "2:10"
    assert PvPRepository.pair_key(2, 10) == "2:10"
