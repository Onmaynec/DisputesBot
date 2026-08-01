# Changelog

## 0.8.0 — 2026-08-01

### Added

- Seasonal PvP title shop through `/shop`.
- Six cosmetic titles gated by season points and purchased with PvP tokens.
- Transactional `/buy` flow with idempotent ownership checks.
- `/inventory` for owned titles and current token balance.
- `/equip` for selecting or clearing the active title.
- Equipped title display in `/season`.
- PostgreSQL tables `pvp_title_purchases` and `pvp_title_loadouts`.
- Alembic migration `0005_cosmetic_titles`.

### Reliability

- Profile row locking serializes purchases for one user.
- Token deduction and title ownership are committed in one transaction.
- Duplicate purchases never charge tokens twice.
- The first purchased title is equipped automatically.
- Locked and unaffordable purchases leave the wallet unchanged.
- Catalog definitions remain code-backed and deterministic.

### Privacy and compatibility

- `/delete_me` explicitly clears title purchases and loadouts.
- Titles are cosmetic and never affect matchmaking, judging or Elo.
- Existing v0.7 wallets, daily claims and season points remain compatible.
- No new runtime dependency is required.

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
