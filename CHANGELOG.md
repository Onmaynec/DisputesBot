# Changelog

## 0.16.0 — 2026-08-02

### Added

- `/season_recap [season]` with a private full-season PvP summary.
- `/compare_seasons [older newer]` with automatic comparison of the two latest seasons.
- `/career_records` with personal best final Elo, peak Elo, wins, games, win rate, rating gain and win streak.
- Per-season rated/unrated counts, unique opponents and deterministic favorite opponent.
- Full-season averages for logic, evidence and rebuttal from existing judge scores.
- Claimed ranked reward milestone and token totals inside the season recap.

### Reliability

- Elo paths are reconstructed from stored before/after values plus the final player row.
- Win streaks are calculated chronologically and reset on draws or losses.
- Invalid score payloads are skipped without breaking the remaining recap.
- Favorite-opponent ties use match count and then the lowest stable user ID.
- Best win-rate records prefer seasons with at least five games and safely fall back for shorter careers.
- Season comparison rejects duplicate, unknown, whitespace-containing and overlong season IDs.

### Privacy and compatibility

- Recaps, comparisons and career records are participant-scoped to the requesting Telegram user.
- No new table, Alembic migration, runtime dependency, OpenAI request or background task is introduced.
- Reports reuse existing `pvp_players`, participant `pvp_matches` and ranked reward claim rows.
- Existing v0.15 archives, v0.14 ranked rewards and migration `0008_ranked_rewards` remain compatible.
- `/delete_me` removes all source rows, after which recap and record views disappear automatically.

## 0.15.0 — 2026-08-02

### Added

- `/pvp_career` with cross-season record, win rate, final Elo, peak Elo and rank.
- `/season_archive [season]` with discoverable historical season standings.
- `/hall_of_fame` with one deterministic champion per retained PvP season.
- Per-season starting Elo, net Elo change and highest achieved Elo reconstruction.
- Current-season markers in archive and Hall of Fame views.

### Reliability

- Career peaks are reconstructed from stored before/after Elo values and the current player row.
- Historical standings reuse the same stable ordering as the live leaderboard.
- Season discovery is ordered by latest player activity and capped to bounded result sets.
- Invalid or unknown season names return a safe empty result.
- Career aggregation reads only the requesting user's player rows and participant matches.
- Archive commands never read match transcripts, arguments or judge score payloads.

### Privacy and compatibility

- No new table, Alembic migration, runtime dependency or background task is introduced.
- Career and archive views reuse existing `pvp_players`, `pvp_matches` and public profile labels.
- Deleting a profile removes its source rows and therefore removes it from archive views.
- Existing v0.14 ranked rewards and migration `0008_ranked_rewards` remain compatible.
- Existing v0.13 coaching, v0.12 matchmaking and v0.10 challenges remain compatible.

## 0.14.0 — 2026-08-02

### Added

- `/ranked_rewards` with current league, peak seasonal Elo, wallet balance and every league milestone.
- `/claim_ranked_rewards` for cumulative token rewards from Bronze through the highest reached division.
- Seven deterministic token rewards aligned with the existing league catalog.
- PostgreSQL table `pvp_ranked_reward_claims` and migration `0008_ranked_rewards`.

### Reliability

- Rewards remain locked until the five-match placement is complete.
- Eligibility uses the highest stored seasonal Elo, so later rating loss does not remove an earned milestone.
- Claims lock the seasonal player and progression wallet in one transaction.
- A composite primary key prevents a league reward from being granted twice for the same user and season.
- Repeated claim requests are idempotent and return the unchanged wallet balance.
- Reward tokens do not modify Elo, season points, matchmaking, judging or match outcomes.

### Privacy and compatibility

- Claim audit rows contain only user ID, season, league ID, token amount, claimed Elo and timestamp.
- Match transcripts, arguments and judge scores are never copied into reward storage.
- `/delete_me` removes ranked reward claims before profile deletion; the table also uses `ON DELETE CASCADE`.
- Existing v0.13 private coaching, v0.12 ranked matchmaking, wallets, cosmetics and daily rewards remain compatible.
- No new runtime dependency is introduced.

## 0.13.0 — 2026-08-02

### Added

- `/match_review [match_id]` with a private criterion-by-criterion PvP breakdown.
- `/pvp_coach` with configurable recent-match averages, results and skill trend.
- Deterministic strongest-skill and training-focus selection for logic, evidence and rebuttal.
- Side-specific average totals for the «за» and «против» positions.
- Configurable coaching window through `PVP_COACH_WINDOW_MATCHES`.

### Reliability

- Coaching reads only immutable completed matches from the current season.
- Matches completed by forfeit or timeout without structured judge scores are excluded.
- Trend compares equally sized recent and older samples and requires at least four scored matches.
- Match lookup is participant-scoped, preventing access to another user's review by match ID.
- Invalid or incomplete historical score payloads are skipped instead of breaking a report.
- No additional OpenAI request is made when a coaching report is rendered.

### Privacy and compatibility

- Coaching reports are available only to the Telegram user whose matches are analyzed.
- No new table, migration, runtime dependency or separately stored skill profile is introduced.
- Reports reuse existing `pvp_matches` scores and disappear when match history is deleted.
- Existing v0.12 ranked matchmaking, v0.11 leagues and v0.10 challenges remain compatible.

## 0.12.0 — 2026-08-02

### Added

- `/ranked_queue` for Elo-aware seasonal matchmaking.
- `/queue_status` with mode, waiting time, topic and current ranked Elo window.
- Separate open and ranked Redis queue modes without mixing participants.
- Deterministic widening search window controlled by four environment settings.
- Ranked candidate selection by smallest Elo difference, then waiting time and user ID.

### Reliability

- Placement players are matched only with other placement players.
- Existing serialized queue entries remain valid and default to the open queue mode.
- The oldest participant's search window widens in fixed steps and is capped.
- Blocklist, active-match locks, queue TTL and single-player queue replacement remain enforced.
- Failed match creation restores both participants to the queue.
- Ordinary `/queue` behavior remains first-waiting-first while ranked matching prefers Elo proximity.

### Privacy and compatibility

- Ranked queue metadata exists only in Redis and expires with the existing queue TTL.
- The temporary snapshot contains mode, current Elo, completed-game count, topic and enqueue time.
- No PostgreSQL table, Alembic migration or runtime dependency is introduced.
- `/leave_queue` and `/delete_me` remove both open and ranked queue entries.
- Existing v0.11 leagues, v0.10 challenges and release automation remain compatible.

## 0.11.0 — 2026-08-02

### Added

- Five-match ranked placement before a visible division is assigned.
- Seven deterministic Elo divisions from Bronze to Grandmaster.
- `/league` with rank, record, recent form, recent Elo delta and promotion progress.
- `/league_top` with division-aware season standings.
- `/league_distribution` with player counts and percentages per division.

### Reliability

- Divisions are derived from existing seasonal Elo and are never stored separately.
- League ranking reuses stable rating, games, update time and user ID tie-breakers.
- Recent Elo delta ignores unrated anti-farming matches.
- Recent form is calculated only from immutable completed matches in the current season.
- Placement players remain visible in standings without receiving a premature division.

### Privacy and compatibility

- No new table, migration, runtime dependency or personal-data category is introduced.
- Match transcripts, arguments and judge scores are not exposed by league views.
- Existing v0.10 challenges, migration `0007_challenges` and release automation remain compatible.
- League commands do not modify matchmaking, judging, rewards or Elo calculation.

## 0.10.0 — 2026-08-02

### Added

- Durable personal PvP challenges through `/challenge`.
- PostgreSQL-backed `/challenges` inbox and outbox.
- `/accept_challenge`, `/decline_challenge` and `/cancel_challenge` lifecycle commands.
- Reply-based targeting and explicit Telegram user ID targeting.
- Configurable challenge expiration through `PVP_CHALLENGE_TTL_HOURS`.
- PostgreSQL table `pvp_challenges` and migration `0007_challenges`.
- Automated tagged GitHub Releases with wheel and source distribution assets.

### Reliability

- One active challenge is allowed per pair and season in either direction.
- An `accepting` reservation prevents duplicate concurrent match creation.
- Stale acceptance reservations recover automatically after five minutes.
- Match creation reuses the existing Redis user locks, blocklist checks and PvP engine.
- Failed match startup releases the challenge back to pending state.
- Expired challenges are finalized lazily during inbox and lifecycle operations.

### Privacy and compatibility

- Blocklist checks apply during challenge creation and acceptance.
- Challenges store only participant IDs, season, topic, status and timestamps.
- `/delete_me` removes incoming and outgoing challenges before profile deletion.
- Existing v0.9 profiles, social settings, cosmetics, progression and matches remain compatible.
- No new runtime dependency is required.

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
