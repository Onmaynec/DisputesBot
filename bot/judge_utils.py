from __future__ import annotations

import json
import random

from .models import DebateSession


def anonymize_history(session: DebateSession) -> tuple[str, str]:
    participant_a = random.SystemRandom().choice(("user", "bot"))
    labels = {
        participant_a: "A",
        "bot" if participant_a == "user" else "user": "B",
    }
    payload = [
        {
            "participant": labels[item.author],
            "text": item.text,
            "round_number": item.round_number,
        }
        for item in session.history
    ]
    return json.dumps(payload, ensure_ascii=False, indent=2), participant_a


def translate_winner(winner: str, participant_a: str) -> str:
    if winner == "draw":
        return "draw"
    if winner == "A":
        return participant_a
    return "bot" if participant_a == "user" else "user"
