# Changelog

## 0.4.0 — 2026-08-01

### Added

- Async SQLAlchemy repository for PostgreSQL profiles and debate archives.
- Alembic configuration and initial database migration.
- Idempotent v0.2/v0.3 JSON profile importer with dry-run mode.
- `/privacy` and confirmed `/delete_me` flows.
- `/export` for current and archived debates in Markdown.
- PostgreSQL service and healthcheck in Docker Compose.
- PostgreSQL migration checks in the Python 3.11/3.13 CI matrix.

### Changed

- Redis now stores only active and temporary state.
- Persistent leaderboard, statistics, achievements and history use PostgreSQL.
- Profile and archive updates are transactional and keyed by Telegram `user_id`/`session_id`.

### Compatibility

- Existing Redis keys and active v0.3 sessions remain compatible.
- `data/leaderboard.json` is supported as a one-time import source.

## 0.3.0 — 2026-08-01

### Added

- Debate history, rematches and fallacy analysis.
- XP, levels, titles and nine achievements.
- Win streaks and criterion averages.
- Backward-compatible JSON profiles.

## 0.2.0 — 2026-08-01

### Added

- Redis-backed restoration of active debates and user preferences.
- Per-user local and distributed request locks.
- Redis-backed fixed-window rate limiting.
- Strict Pydantic Structured Outputs and independent judging.
