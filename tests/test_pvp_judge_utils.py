import json

from bot.models import Stance
from bot.pvp_judge_utils import anonymize_pvp_match, winner_from_alias
from bot.pvp_models import PvPMatch, PvPParticipant


def test_pvp_anonymization_hides_ids_and_names() -> None:
    match = PvPMatch(
        topic="Тема",
        season="season-1",
        pro=PvPParticipant(user_id=10, display_name="Alice", stance=Stance.PRO),
        con=PvPParticipant(user_id=20, display_name="Bob", stance=Stance.CON),
    )
    match.add_argument(10, "Первый тезис")
    match.add_argument(20, "Первое возражение")

    raw, participant_a = anonymize_pvp_match(match, participant_a_user_id=20)
    payload = json.loads(raw)

    assert participant_a == 20
    assert [item["participant"] for item in payload] == ["B", "A"]
    assert "Alice" not in raw
    assert "Bob" not in raw
    assert '"user_id"' not in raw


def test_anonymous_winner_maps_back_to_user_id() -> None:
    assert winner_from_alias(
        "A", participant_a_user_id=20, participant_b_user_id=10
    ) == 20
    assert winner_from_alias(
        "B", participant_a_user_id=20, participant_b_user_id=10
    ) == 10
    assert (
        winner_from_alias(
            "draw", participant_a_user_id=20, participant_b_user_id=10
        )
        is None
    )
