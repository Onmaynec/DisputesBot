<div align="center">

# ⚔️ DisputesBot v0.19

**Telegram-бот для тренировки дебатов, логики и критического мышления**

![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![aiogram](https://img.shields.io/badge/aiogram-3.30.0-2CA5E0)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-goals%20%26%20rewards-336791)
![Redis](https://img.shields.io/badge/Redis-ranked%20matchmaking-red)
![Version](https://img.shields.io/badge/version-0.19.0-brightgreen)

</div>

## ✨ Новое в v0.19

- 🎁 `/goal_rewards` — приватная доска наград сезонных целей;
- ✅ `/claim_goal_rewards` — получить все доступные токены и season points;
- 🔒 одна награда на метрику для каждого пользователя и сезона;
- 🛡️ антифарм-пороги для Elo, побед, матчей, win rate, серий и судейских навыков;
- ♻️ повторный claim полностью идемпотентен;
- 🗄️ таблица `pvp_goal_reward_claims` и миграция `0010_goal_rewards`;
- 📱 новые команды автоматически добавляются в Telegram command menu.

Все возможности v0.18 сохранены: приватные сезонные цели, record books, season
insights, архивы, ranked rewards, coaching, Elo-aware matchmaking, вызовы и косметика.

## 🎁 Награды сезонных целей

```text
/goal_rewards
/claim_goal_rewards
```

`/goal_rewards` показывает:

- активные, завершённые и уже полученные цели;
- baseline, target и фактическую сложность цели;
- размер награды в PvP-токенах и season points;
- минимальный прирост, если цель слишком мала для награды;
- текущий progression wallet.

`/claim_goal_rewards` сначала обновляет завершение целей из авторитетных Elo,
сезонной статистики и сохранённых judge scores, затем одной PostgreSQL-транзакцией:

1. блокирует профиль пользователя;
2. блокирует сезонные цели и существующие claim-строки;
3. блокирует progression wallet;
4. создаёт claim для каждой подходящей метрики;
5. добавляет токены и season points.

Составной ключ `(user_id, season, metric)` исключает двойное начисление. Повторное
создание или повышение уже оплаченной метрики в том же сезоне не выдаёт новую награду.

### Каталог наград

| Метрика | Минимальный прирост | Токены | Season points |
|---|---:|---:|---:|
| Elo | +50 Elo | 25 | 40 |
| Лига | переход к более высокой границе | 35 | 60 |
| Победы | +3 | 20 | 30 |
| Матчи | +5 | 15 | 25 |
| Win rate | +5 п.п. | 25 | 40 |
| Серия побед | +2 | 25 | 40 |
| Logic | +0.5 | 30 | 45 |
| Evidence | +0.5 | 30 | 45 |
| Rebuttal | +0.5 | 30 | 45 |

Маленькие цели остаются допустимыми как личные ориентиры, но не создают claimable
reward. Цели по лиге считаются значимыми, когда target выше baseline Elo.

## 🎯 Сезонные цели

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
```

Одновременно можно держать до пяти активных целей. Completion фиксируется навсегда:
последующее падение Elo, win rate или среднего навыка не отменяет достигнутую цель.
Win-rate требует минимум пять матчей, а skill-goals — минимум три корректно оценённых
матча. Рекомендации детерминированы и не вызывают OpenAI.

## 📊 Итоги и рекорды

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

- `season_recap` — приватный полный отчёт сезона;
- `compare_seasons` — сравнение двух сезонов пользователя;
- `career_records` — лучшие сезонные показатели;
- `pvp_records` — приватные рекорды отдельных матчей и соперников;
- `season_records` — публичные агрегированные рекорды сезона;
- `pvp_career` — карьера по сохранённым сезонам;
- `season_archive` — исторические таблицы;
- `hall_of_fame` — чемпионы сезонов.

Публичные представления не раскрывают темы, match ID, аргументы, стенограммы,
вердикты или judge score payload.

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
Ranked rewards выдаются один раз за достигнутые дивизионы и не зависят от goal rewards.

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
/shop
/buy ITEM_ID
/inventory
/equip ITEM_ID
/unequip title|badge
```

Daily, ranked rewards и goal rewards используют общий сезонный progression wallet.
Косметика и любые награды не меняют Elo, matchmaking, judge verdict или исход матча.

## 🔐 Приватность

Goal reward claim хранит только:

- Telegram user ID;
- season ID;
- фиксированный metric ID;
- числовые baseline и target;
- reward tokens и reward points;
- время completion и claim.

Темы матчей, аргументы, стенограммы, verdict reason и judge score payload в claim
не копируются. `/goal_rewards` доступна только владельцу аккаунта.

`/delete_me` удаляет профиль, архивы, PvP-рейтинг и матчи, progression wallet,
daily/ranked/goal reward claims, сезонные цели, косметику, публичность, вызовы,
blocklist, очереди и активные Redis-сессии. Reward claims используют
`ON DELETE CASCADE`.

## 🗄️ Хранилища

### PostgreSQL

Профили, архивы, сезонный Elo, завершённые матчи, judge scores, progression wallets,
daily claims, ranked rewards, goals, goal reward claims, косметика, profile visibility,
вызовы, blocklist и moderation audit.

### Redis

Активные споры и PvP-матчи, приглашения, обычная и ranked queue, временные Elo-снимки,
turn deadlines, request locks, rate limit и подтверждения удаления.

## ⚙️ Установка

```bash
git clone https://github.com/Onmaynec/DisputesBot.git
cd DisputesBot
cp .env.example .env
```

Заполните минимум `BOT_TOKEN` и `OPENAI_API_KEY`.

```bash
docker compose up -d postgres redis
pip install -e ".[dev]"
alembic upgrade head
python -m bot.main
```

Полный Docker-запуск:

```bash
docker compose up --build -d
```

## ⬆️ Обновление с v0.18

```bash
git pull
pip install -e ".[dev]"
alembic upgrade head
```

v0.19 добавляет миграцию `0010_goal_rewards`. Существующие цели, Elo, матчи,
кошельки, ranked rewards и косметика не изменяются.

## 🧪 Проверки

```bash
ruff check .
python -m compileall -q bot tests migrations
alembic upgrade head
pytest -q
```

GitHub Actions проверяет Python 3.11 и 3.13 с PostgreSQL 17.

## 📦 Релизы

После merge в `main` workflow `.github/workflows/release.yml` читает версию из
`pyproject.toml`, собирает wheel и source distribution, извлекает notes из
`CHANGELOG.md`, создаёт тег `vX.Y.Z` и публикует GitHub Release.

## 📄 Лицензия

MIT
