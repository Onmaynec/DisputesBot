# Changelog

## 0.3.0 — 2026-08-01

### Added

- `/history` with up to ten recent saved debates.
- `/rematch` for restarting the last topic and mode.
- `/fallacies` with strict structured logical-fallacy analysis.
- `/achievements` with nine unlockable achievements.
- XP, levels, win streaks and criterion averages in `/stats`.
- Compact transcripts in the profile archive.
- Idempotent archive updates based on a stable session identifier.

### Changed

- The v0.2 JSON leaderboard is now a backward-compatible user profile store.
- Tournament results and regular debates share one history and progression system.
- Starting a new debate archives an unfinished debate instead of silently overwriting it.
- `/judge` saves or updates the current debate in history.

## 0.2.0 — 2026-08-01

- Redis-backed sessions, request locks and rate limiting.
- Independent anonymized judging and strict Pydantic outputs.
- Leaderboard keyed by Telegram user ID.
- `/difficulty`, `/cancel` and `/stats`.
