# Changelog

## 0.5.0 — 2026-08-01

### Added

- Direct PvP duel invitations with inline acceptance.
- Redis-backed matchmaking queue and active match restoration.
- Strict turn-based PvP flow with three arguments per participant.
- `/duel_status`, `/cancel_duel`, `/forfeit` and `/leave_queue`.
- Independent anonymized A/B judging for human-vs-human debates.
- Seasonal Elo ratings with an initial rating of 1000 and K-factor 32.
- `/rating`, `/pvp_leaderboard` and `/duel_history`.
- PostgreSQL tables for seasonal players and immutable PvP match results.
- Alembic migration `0002_pvp`.

### Reliability

- A participant cannot be assigned to two active matches.
- Match creation locks both user IDs in stable order.
- Match judging has a dedicated distributed lock.
- Repeated persistence of the same `match_id` is idempotent.
- Elo changes are symmetric and sum to zero.
- Old v0.4 Redis keys and solo-debate APIs remain compatible.

## 0.4.0 — 2026-08-01

- PostgreSQL profiles and debate archives.
- Alembic and idempotent JSON import.
- Privacy controls, account deletion and Markdown export.
- PostgreSQL CI on Python 3.11 and 3.13.

## 0.3.0 — 2026-08-01

- Debate history, rematches, fallacy analysis, XP and achievements.

## 0.2.0 — 2026-08-01

- Redis sessions, request locks, rate limiting and independent judging.
