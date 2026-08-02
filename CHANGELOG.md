# Changelog

## 0.10.0 — 2026-08-02

### Added

- Five-match ranked placement before a visible division is assigned.
- Seven deterministic Elo divisions from Bronze to Grandmaster.
- `/league` with rank, record, recent form, recent Elo delta and promotion progress.
- `/league_top` with division-aware season standings.
- `/league_distribution` with player counts and percentages per division.

### Reliability

- Divisions are derived from the existing seasonal Elo and never stored separately.
- League ranking reuses stable rating, games, update time and user ID tie-breakers.
- Recent Elo delta ignores unrated anti-farming matches.
- Recent form is calculated only from immutable completed matches in the current season.
- Placement players remain visible in standings without receiving a premature division.

### Privacy and compatibility

- No new table, migration, runtime dependency or personal-data category is introduced.
- League commands reuse the same public aggregate rating data as the PvP leaderboard.
- Match transcripts, arguments and judge scores are not exposed by league views.
- Existing v0.9 profiles, social settings, cosmetics and progression remain compatible.

## 0.9.0 — 2026-08-01

### Added

- `/rivals` with the five most frequent opponents of the current season.
- `/head_to_head` with shared match record, rated count, Elo delta and recent topics.
- Foreign profile lookup through `/pvp_profile user_id` or a replied Telegram message.
- Opt-in profile visibility through `/profile_visibility public|private`.
- Block-aware profile access in both directions.
- PostgreSQL table `pvp_profile_settings` and migration `0006_social_profiles`.

### Reliability

- Rival and head-to-head data is derived from immutable completed PvP matches.
- Only matches containing the requesting user are included in social statistics.
- Rating delta is summed from stored before/after values and excludes unrated matches.
- Stable sorting uses match count, last match time and opponent ID.
- Existing v0.8 self-profile behavior remains available without public opt-in.

### Privacy and compatibility

- Profiles are private by default and require explicit public opt-in.
- Token balances are never shown to another user.
- A block by either participant prevents foreign profile access.
- `/delete_me` removes the visibility setting; the table also uses `ON DELETE CASCADE`.
- Existing profiles, Elo, matches, progression and cosmetics remain compatible.
- No new runtime dependency is required.

## 0.8.0 — 2026-08-01

### Added

- Seasonal PvP cosmetic shop powered by existing progression tokens.
- Eight catalog items: four badges and four public titles.
- `/shop`, `/buy`, `/inventory`, `/equip` and `/unequip` commands.
- `/pvp_profile` public card with Elo, season tier, record and equipped cosmetics.
- Separate seasonal inventory and loadout tables.
- Alembic migration `0005_cosmetics`.

### Reliability

- Purchases lock the user profile and progression wallet in one transaction.
- Duplicate purchases are idempotent and never charge tokens twice.
- Season-point requirements are checked server-side before token deduction.
- A first item in each slot is automatically equipped; later loadout changes are explicit.
- Cosmetic rewards never modify matchmaking, judging, match outcomes or Elo.

### Privacy and compatibility

- Inventory and loadouts use `ON DELETE CASCADE` with the user profile.
- Cosmetics contain catalog IDs only and store no debate text or opponent data.
- Existing v0.7 wallets and token balances remain compatible.
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
