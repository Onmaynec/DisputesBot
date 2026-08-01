from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EloChange:
    rating_a_before: int
    rating_b_before: int
    rating_a_after: int
    rating_b_after: int

    @property
    def delta_a(self) -> int:
        return self.rating_a_after - self.rating_a_before

    @property
    def delta_b(self) -> int:
        return self.rating_b_after - self.rating_b_before


def expected_score(rating_a: int, rating_b: int) -> float:
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400))


def calculate_elo(
    rating_a: int,
    rating_b: int,
    score_a: float,
    *,
    k_factor: int = 32,
) -> EloChange:
    if score_a not in {0.0, 0.5, 1.0}:
        raise ValueError("Elo score must be 0, 0.5 or 1")
    if k_factor <= 0:
        raise ValueError("Elo K-factor must be positive")
    delta = round(k_factor * (score_a - expected_score(rating_a, rating_b)))
    return EloChange(
        rating_a_before=rating_a,
        rating_b_before=rating_b,
        rating_a_after=rating_a + delta,
        rating_b_after=rating_b - delta,
    )
