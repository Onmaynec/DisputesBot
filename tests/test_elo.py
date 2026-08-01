from bot.elo import calculate_elo, expected_score


def test_equal_players_exchange_symmetric_elo() -> None:
    change = calculate_elo(1000, 1000, 1.0)

    assert change.rating_a_after == 1016
    assert change.rating_b_after == 984
    assert change.delta_a + change.delta_b == 0


def test_draw_against_stronger_player_rewards_underdog() -> None:
    change = calculate_elo(900, 1100, 0.5)

    assert change.rating_a_after > 900
    assert change.rating_b_after < 1100
    assert change.delta_a + change.delta_b == 0
    assert expected_score(900, 1100) < 0.5
