<div align="center">

# ⚔️ DisputesBot v0.21

**Telegram-бот для тренировки дебатов, логики и критического мышления**

![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![aiogram](https://img.shields.io/badge/aiogram-3.30.0-2CA5E0)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pass%20cosmetics-336791)
![Redis](https://img.shields.io/badge/Redis-ranked%20matchmaking-red)
![Version](https://img.shields.io/badge/version-0.21.0-brightgreen)

</div>

## ✨ Новое в v0.21

- 🎨 семь эксклюзивных предметов сезонного пропуска;
- 🎟 `/season_pass` показывает токены и косметику каждого уровня;
- 🎁 `/claim_season_pass` выдаёт токены и предметы одной транзакцией;
- 🖼 `/pass_collection` показывает коллекцию, unlock и equipped status;
- 🎖 первый предмет свободного badge/title-слота экипируется автоматически;
- ♻️ старые claims v0.20 получают пропущенную косметику без повторных токенов;
- 🗄️ migration `0012_season_pass_cosmetics` сохраняет item ID и время выдачи.

Все возможности v0.20 сохранены: season pass, goal rewards, measurable goals,
record books, season insights, ranked rewards, coaching, Elo matchmaking, challenges
и магазин косметики.

## 🎟 Сезонный пропуск

```text
/season_pass
/claim_season_pass
/pass_collection
```

| Уровень | Points | Токены | Эксклюзив |
|---|---:|---:|---|
| 🌱 Новичок | 100 | 10 | 🌿 Росток сезона |
| 🥉 Претендент | 250 | 15 | Восходящий голос |
| 🥈 Челленджер | 500 | 25 | 🪶 Серебряное перо |
| 🥇 Ветеран | 900 | 35 | Ветеран пропуска |
| 💎 Элита | 1400 | 50 | 🔷 Кристалл аргумента |
| 👑 Чемпион | 2000 | 70 | Чемпион сезона |
| 🏆 Легенда | 3000 | 100 | 🏆 Трофей легенды |

`/claim_season_pass` блокирует профиль, progression wallet, pass claims, cosmetic
inventory и loadout в одной PostgreSQL-транзакции. Составной ключ
`(user_id, season, tier_id)` исключает повторную token-награду.

Для claims, созданных в v0.20, повторная команда выдаёт только отсутствующий предмет.
Токены повторно не начисляются. Если предмет уже есть, audit row восстанавливается без
дубликата inventory.

Pass cosmetics:

- не отображаются в обычном `/shop`;
- не покупаются через `/buy`;
- находятся в существующем сезонном `/inventory` storage;
- поддерживают `/equip item_id`;
- отображаются в PvP-профиле, если экипированы.

Награды не добавляют season points и не меняют Elo, matchmaking, judging или исход
матча.

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

Одновременно можно держать до пяти активных целей. Completion остаётся sticky после
падения Elo, win rate или skill average. Goal rewards используют антифарм-пороги и
начисляются один раз на metric и season.

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

Личные отчёты доступны только владельцу. Публичные boards не раскрывают темы,
match ID, аргументы, стенограммы, verdict reason или judge-score payload.

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

Первые пять матчей считаются placement. Ranked matchmaking расширяет Elo-window по
мере ожидания и не смешивает placement-игроков с откалиброванными.

## 🎓 Coaching

```text
/match_review [MATCH_ID]
/pvp_coach
```

Coaching использует сохранённые logic, evidence и rebuttal. Чужой review получить
нельзя, повторный OpenAI-запрос для отчёта не выполняется.

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

Профили приватны по умолчанию. Blocklist применяется к профилям, приглашениям,
очередям, рематчам и персональным challenges.

## 🪙 Прогресс и косметика

```text
/daily
/daily_claim
/season
/season_top
/season_pass
/claim_season_pass
/pass_collection
/shop
/buy ITEM_ID
/inventory
/equip ITEM_ID
/unequip title|badge
```

Daily, ranked rewards, goal rewards и season pass используют общий сезонный wallet.
Косметика и награды не меняют PvP Elo или judge verdict.

## 🚀 Запуск

Требования: Python 3.11+, PostgreSQL, Redis, Telegram bot token и OpenAI-compatible
API key.

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

Создайте `.env` на основе `.env.example`, затем:

```bash
alembic upgrade head
python -m bot.main
```

Обновление с v0.20:

```bash
git pull
pip install -e ".[dev]"
alembic upgrade head
```

## ✅ Проверки

```bash
ruff check .
python -m compileall bot tests migrations
pytest
```

CI выполняет install, Ruff, compileall, Alembic и полный pytest на Python 3.11 и
3.13 с PostgreSQL 17.

## 🔐 Приватность

Season-pass claim хранит user ID, season, tier ID, points requirement, token reward,
claimed points, точный cosmetic item ID и timestamps. Debate text, topic, match ID,
transcript, verdict и judge-score payload не копируются.

`/delete_me` удаляет профиль, матчи, progression wallet, daily/ranked/goal/pass claims,
цели, косметику, profile visibility, challenges, blocklist, queues и Redis-сессии.
Claim и inventory tables используют `ON DELETE CASCADE`.

## 📦 Релизы

Push в `main` запускает release workflow. Версия читается из `pyproject.toml`, wheel и
source distribution собираются автоматически, notes берутся из
`release-notes/<version>.md` с fallback на `CHANGELOG.md`.

## 📄 Лицензия

MIT.
