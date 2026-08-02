<div align="center">

# ⚔️ DisputesBot v0.20

**Telegram-бот для тренировки дебатов, логики и критического мышления**

![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![aiogram](https://img.shields.io/badge/aiogram-3.30.0-2CA5E0)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-season%20pass-336791)
![Redis](https://img.shields.io/badge/Redis-ranked%20matchmaking-red)
![Version](https://img.shields.io/badge/version-0.20.0-brightgreen)

</div>

## ✨ Новое в v0.20

- 🎟 `/season_pass` — приватный сезонный пропуск из семи уровней;
- 🎁 `/claim_season_pass` — получить все разблокированные награды одной транзакцией;
- 📈 уровни открываются на 100, 250, 500, 900, 1400, 2000 и 3000 season points;
- 🔒 каждый уровень выдаёт награду один раз на пользователя и сезон;
- ♻️ повторный claim идемпотентен, а новый прогресс оплачивает только новые уровни;
- 🪙 пропуск начисляет только токены и не может сам открыть следующий уровень;
- 🗄️ таблица `pvp_season_pass_claims` и миграция `0011_season_pass`;
- 📝 release workflow поддерживает versioned notes в `release-notes/<version>.md`.

Все функции v0.19 сохранены: награды сезонных целей, измеримые goals, record books,
season insights, архивы, ranked rewards, coaching, Elo matchmaking, вызовы и косметика.

## 🎟 Сезонный пропуск

```text
/season_pass
/claim_season_pass
```

| Уровень | Season points | Токены |
|---|---:|---:|
| 🌱 Новичок | 100 | 10 |
| 🥉 Претендент | 250 | 15 |
| 🥈 Челленджер | 500 | 25 |
| 🥇 Ветеран | 900 | 35 |
| 💎 Элита | 1400 | 50 |
| 👑 Чемпион | 2000 | 70 |
| 🏆 Легенда | 3000 | 100 |

`/season_pass` показывает текущие season points, баланс токенов, прогресс каждого
уровня, доступные награды и следующий milestone.

`/claim_season_pass` блокирует профиль и progression wallet в одной PostgreSQL-
транзакции, создаёт audit rows для всех новых уровней и добавляет только токены.
Составной ключ `(user_id, season, tier_id)` исключает двойное начисление.

Награды пропуска не добавляют season points, не меняют Elo, matchmaking, судейство
или результат матча. Каждый новый PvP-сезон имеет отдельный прогресс и claim history.

## 🎯 Сезонные цели и награды

```text
/goals
/set_goal elo 1200
/set_goal league diamond
/set_goal wins 20
/set_goal matches 30
/set_goal win_rate 60
/set_goal streak 5
/set_goal logic 8.0
/set_goal evidence 8.0
/set_goal rebuttal 8.0
/delete_goal elo
/goal_suggest
/goal_rewards
/claim_goal_rewards
```

Одновременно можно держать до пяти активных целей. Completion фиксируется навсегда:
падение Elo, win rate или среднего навыка не отменяет достигнутую цель.

Goal rewards используют антифарм-пороги и могут начислять токены и season points.
Одна метрика оплачивается только один раз за сезон. Season-pass rewards используют
уже накопленные points и начисляют только токены.

## 📊 Итоги, архивы и рекорды

```text
/season_recap [season]
/compare_seasons [older newer]
/career_records
/pvp_records
/season_records [season]
/pvp_career
/season_archive [season]
/hall_of_fame
```

- приватные итоги и сравнения сезонов;
- карьерные рекорды и Elo-пути;
- персональные матчевые рекорды;
- публичные агрегированные рекорды сезона;
- исторические standings и чемпионы.

Публичные представления не раскрывают темы, match ID, аргументы, стенограммы,
вердикты или judge-score payload.

## 🏆 Ranked PvP

```text
/ranked_queue тема
/queue_status
/leave_queue
/rating
/league
/league_top
/league_distribution
/ranked_rewards
/claim_ranked_rewards
```

Первые пять матчей считаются placement. Ranked matchmaking расширяет допустимый Elo
диапазон по мере ожидания и не смешивает placement-игроков с откалиброванными.

## 🎓 Приватный coaching

```text
/match_review [MATCH_ID]
/pvp_coach
```

Coaching использует сохранённые logic, evidence и rebuttal полных PvP-матчей.
Чужой match review получить нельзя. Повторный запрос к OpenAI не выполняется.

## ⚔️ Дуэли и социальные функции

```text
/duel [тема]
/queue [тема]
/rematch_duel
/duel_status
/cancel_duel
/forfeit
/duel_history
/pvp_stats
/rivals
/head_to_head USER_ID
/pvp_profile [USER_ID]
/profile_visibility public|private
/challenge USER_ID тема
/challenges
/accept_challenge ID
/decline_challenge ID
/cancel_challenge ID
/block USER_ID
/unblock USER_ID
/blocked
/report категория комментарий
/my_reports
```

Профили приватны по умолчанию. Blocklist применяется к просмотру профилей,
приглашениям, очередям, рематчам и персональным вызовам.

## 🪙 Прогресс и косметика

```text
/daily
/daily_claim
/season
/season_top
/season_pass
/claim_season_pass
/shop
/buy ITEM_ID
/inventory
/equip ITEM_ID
/unequip title|badge
```

Daily quests, ranked rewards, goal rewards и season pass используют общий сезонный
progression wallet. Косметика и награды не меняют PvP Elo или judge verdict.

## 🚀 Запуск

Требования:

- Python 3.11+;
- PostgreSQL;
- Redis;
- Telegram bot token;
- OpenAI-compatible API key.

```bash
git clone https://github.com/Onmaynec/DisputesBot.git
cd DisputesBot
python -m venv .venv
```

Windows:

```powershell
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

Linux/macOS:

```bash
source .venv/bin/activate
pip install -e ".[dev]"
```

Создайте `.env` на основе `.env.example`, затем примените миграции и запустите бота:

```bash
alembic upgrade head
python -m bot.main
```

## ✅ Проверки

```bash
ruff check .
python -m compileall bot tests
pytest
```

CI выполняет install, Ruff, compileall, полную Alembic-цепочку и pytest на Python
3.11 и 3.13 с PostgreSQL 17.

## 🔐 Приватность

Season-pass claim хранит только:

- Telegram user ID;
- season ID;
- фиксированный tier ID;
- требование по season points;
- размер token reward;
- balance season points в момент claim;
- время claim.

Темы, match ID, аргументы, стенограммы, verdict reason и judge-score payload в claim
не копируются. `/season_pass` доступна только владельцу аккаунта.

`/delete_me` удаляет профиль, архивы, PvP-рейтинг и матчи, progression wallet,
daily/ranked/goal/season-pass claims, сезонные цели, косметику, публичность, вызовы,
blocklist, очереди и активные Redis-сессии. Claim tables используют
`ON DELETE CASCADE`.

## 🗄️ Хранилища

**PostgreSQL:** профили, архивы, сезонный Elo, завершённые матчи, judge scores,
progression wallets, daily claims, ranked rewards, goals, goal rewards, season-pass
claims, косметика, profile visibility, challenges, blocklist и moderation audit.

**Redis:** активные дебаты и PvP-матчи, очереди, приглашения, locks, rate limits,
deadlines и временные подтверждения приватных операций.

## 📦 Релизы

Push в `main` запускает release workflow. Версия читается из `pyproject.toml`, wheel и
source distribution собираются автоматически, а notes берутся из
`release-notes/<version>.md` или, для старых версий, из `CHANGELOG.md`.

## 📄 Лицензия

MIT.
