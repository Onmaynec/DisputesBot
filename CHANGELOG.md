# Changelog

## 0.2.0 — 2026-08-01

### Added

- Redis-backed restoration of active debates and user preferences.
- Per-user local and distributed request locks.
- Redis-backed fixed-window rate limiting.
- Topic and argument length limits.
- Strict Pydantic Structured Outputs for LLM responses.
- Independent anonymized judge with a separately configurable model.
- `/difficulty`, `/cancel` and `/stats` commands.
- Tournament win/draw/loss statistics.
- Tests for locking, rate limiting, Redis restoration and leaderboard migration.

### Changed

- Leaderboard entries are keyed by Telegram `user_id`.
- Old username-keyed leaderboard entries are migrated on read/write.
- Docker Compose now starts a persistent Redis service.
