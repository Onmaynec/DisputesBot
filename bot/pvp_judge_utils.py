from __future__ import annotations

import json
import secrets

from .pvp_models import PvPMatch


def anonymize_pvp_match(
    match: PvPMatch,
    *,
    participant_a_user_id: int | None = None,
) -> tuple[str, int]:
    if participant_a_user_id is None:
        participant_a_user_id = (
            match.pro.user_id if secrets.randbelow(2) == 0 else match.con.user_id
        )
    match.participant(participant_a_user_id)
    participant_b_user_id = match.opponent(participant_a_user_id).user_id
    aliases = {participant_a_user_id: "A", participant_b_user_id: "B"}
    payload = [
        {
            "participant": aliases[item.user_id],
            "turn_number": item.turn_number,
            "text": item.text,
        }
        for item in match.arguments
    ]
    return json.dumps(payload, ensure_ascii=False, indent=2), participant_a_user_id


def winner_from_alias(
    winner: str,
    *,
    participant_a_user_id: int,
    participant_b_user_id: int,
) -> int | None:
    if winner == "draw":
        return None
    if winner == "A":
        return participant_a_user_id
    if winner == "B":
        return participant_b_user_id
    raise ValueError("Unknown anonymous winner")
