# Changelog

## 0.6.0 — 2026-08-01

### Added

- Persistent directional PvP blocklist with `/block`, `/unblock` and `/blocked`.
- Block-aware open invitations, personal rematches and matchmaking queue.
- Structured PvP reports with deterministic report IDs and `/my_reports`.
- Moderator-only report review commands with decision audit fields.
- Per-turn deadlines, Redis active-match index and background timeout sweep.
- `/rematch_duel` for the latest opponent with optional topic replacement.
- Pair-based Elo anti-farming window and unrated history entries.
- `/pvp_health` with aggregate active-match, queue and open-report counts.
- Alembic migration `0003_moderation`.

### Reliability

- Timeout finalization is guarded by the existing distributed match lock.
- A timeout before the first move cancels without rating changes.
- A timeout after play begins records a deterministic loss for the inactive player.
- Pair rating checks are side-independent and player rows are locked in stable ID order.
- Duplicate reports and repeated match persistence are idempotent.
- Account deletion anonymizes report ownership and clears blocklist relations.

### Compatibility

- Existing v0.5 matches are assigned a `pair_key` during migration.
- Solo debates, v0.5 PvP commands, profiles and archives remain compatible.
- No new runtime dependency is required.

## 0.5.0 — 2026-08-01

- Human PvP invitations, matchmaking and Redis restoration.
- Strict six-turn flow, independent A/B judging and seasonal Elo.
- PostgreSQL PvP history and migration `0002_pvp`.

## 0.4.0 — 2026-08-01

- PostgreSQL profiles and debate archives.
- Alembic, privacy controls, account deletion and Markdown export.

## 0.3.0 — 2026-08-01

- Debate history, rematches, fallacy analysis, XP and achievements.

## 0.2.0 — 2026-08-01

- Redis sessions, request locks, rate limiting and independent judging.
