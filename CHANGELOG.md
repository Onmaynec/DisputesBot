# Changelog

## 0.7.0 — 2026-08-01

### Added

- Deterministic daily PvP quest set with `/daily`.
- Idempotent transactional reward collection through `/daily_claim`.
- Separate PvP tokens, season points and daily claim streaks.
- Six fixed season tiers and `/season` progression view.
- `/season_top` leaderboard ordered by season points and stable tie-breakers.
- `/pvp_stats` with rated/unrated split, win rate, opponent diversity and streaks.
- Side-specific pro/con statistics and configurable recent Elo window.
- PostgreSQL tables `pvp_progression` and `pvp_daily_claims`.
- Alembic migration `0004_progression`.

### Reliability

- Quest definitions are derived from the progression date and survive restarts.
- Progress is calculated from immutable stored PvP matches.
- Profile row locking serializes reward claims for an existing player.
- A composite claim key prevents duplicate rewards per user, season, day and quest.
- Daily streaks advance at most once per progression day.
- Progression rewards never modify PvP Elo or match outcomes.

### Privacy and compatibility

- `/delete_me` removes wallets and claim history before deleting the profile.
- Privacy documentation includes tokens, season points and daily streaks.
- Existing v0.6 profiles, matches, reports and moderation data remain compatible.
- No new runtime dependency is required.

## 0.6.0 — 2026-08-01

- PvP blocklists, reports, moderator audit and turn deadlines.
- Personal rematches, timeout resolution and Elo anti-farming.
- Migration `0003_moderation`.

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
