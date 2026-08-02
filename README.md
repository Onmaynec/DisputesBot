<div align="center">

# ⚔️ DisputesBot v0.17

**Telegram-бот для тренировки дебатов, логики и критического мышления**

![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![aiogram](https://img.shields.io/badge/aiogram-3.30.0-2CA5E0)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-private%20season%20goals-336791)
![Redis](https://img.shields.io/badge/Redis-ranked%20matchmaking-red)
![Version](https://img.shields.io/badge/version-0.17.0-brightgreen)

</div>

## ✨ Новое в v0.17

- 🎯 `/goals` — приватные сезонные цели и прогресс;
- ✍️ `/set_goal МЕТРИКА ЦЕЛЬ` — создать или изменить измеримую цель;
- 🗑 `/delete_goal МЕТРИКА` — удалить цель;
- 🧭 `/goal_suggest` — детерминированные персональные рекомендации;
- 📈 цели по Elo, лиге, победам, матчам, win rate и серии побед;
- 🧠 цели по logic, evidence и rebuttal;
- ✅ sticky completion: достигнутая цель не отменяется после падения показателя;
- 🗄️ миграция `0009_season_goals`.

Все возможности v0.16 сохранены: season recap, сравнение сезонов, карьерные рекорды,
архивы, ranked rewards, coaching, Elo-aware matchmaking, вызовы и косметика.

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
/delete_goal logic
/goal_suggest
```

Одновременно можно держать до пяти активных целей текущего `PVP_SEASON`. Повторный
`/set_goal` для той же метрики заменяет её baseline и target.

Поддерживаемые метрики:

| Метрика | Пример | Условие завершения |
|---|---:|---|
| `elo` | `1200` | текущий сезонный Elo достиг цели |
| `league` | `diamond` | калибровка завершена и достигнут порог лиги |
| `wins` | `20` | число побед достигло цели |
| `matches` | `30` | число матчей достигло цели |
| `win_rate` | `60` | процент побед достиг цели минимум после 5 матчей |
| `streak` | `5` | лучшая серия побед достигла цели |
| `logic` | `8.0` | средняя логика достигла цели минимум после 3 оценённых матчей |
| `evidence` | `8.0` | средние доказательства достигли цели минимум после 3 матчей |
| `rebuttal` | `8.0` | среднее опровержение достигло цели минимум после 3 матчей |

Прогресс вычисляется из авторитетных `pvp_players` и `pvp_matches`. Завершение
фиксируется один раз, поэтому последующее падение Elo, win rate или среднего навыка
не отменяет уже выполненную цель.

Цели не начисляют токены, не меняют Elo и не влияют на matchmaking, судейство или
результат матча. `/goal_suggest` не вызывает OpenAI: рекомендации строятся из
калибровки, следующей лиги, побед, серии и самого слабого навыка.

## 📊 Персональные итоги и рекорды

```text
/season_recap [season]
/compare_seasons [older newer]
/career_records
```

`/season_recap` показывает Elo-путь, ранг, дивизион, rated/unrated, соперников, серию
побед, средние judge skills и полученные ranked rewards. `/compare_seasons` сравнивает
два указанных или два последних сезона. `/career_records` выбирает лучшие сезоны по
Elo, победам, матчам, win rate, приросту и серии.

Эти отчёты доступны только владельцу Telegram user ID и не сохраняются отдельно.

## 🗂 Карьера и сезонный архив

```text
/pvp_career
/season_archive [season]
/hall_of_fame
```

`/pvp_career` показывает личную карьеру по сезонам. `/season_archive` выводит каталог
или исторический топ-10. `/hall_of_fame` показывает чемпиона каждого сезона.
Исторические таблицы используют те же стабильные tie-breakers, что live leaderboard.

## 🎁 Награды рейтинговых лиг

```text
/ranked_rewards
/claim_ranked_rewards
```

После пяти калибровочных матчей игрок может получить накопительные награды до
максимального достигнутого Elo сезона.

| Дивизион | Минимальный Elo | Награда |
|---|---:|---:|
| 🥉 Бронза | 0 | 15 🪙 |
| 🥈 Серебро | 900 | 25 🪙 |
| 🥇 Золото | 1000 | 40 🪙 |
| 💠 Платина | 1100 | 60 🪙 |
| 💎 Алмаз | 1200 | 90 🪙 |
| 🏅 Мастер | 1300 | 130 🪙 |
| 👑 Грандмастер | 1450 | 200 🪙 |

Claim выполняется одной PostgreSQL-транзакцией. Составной ключ
`(user_id, season, league_id)` исключает повторное начисление.

## 🎓 Приватный PvP coaching

```text
/match_review [MATCH_ID]
/pvp_coach
```

`/match_review` показывает приватный разбор собственного оценённого матча.
`/pvp_coach` агрегирует последние оценённые матчи, показывает тренд, сильную сторону
и фокус тренировки. Отчёты используют сохранённые score payload без новых
OpenAI-запросов.

## 🎯 Рейтинговый matchmaking и лиги

```text
/ranked_queue тема
/queue_status
/leave_queue
/league
/league_top
/league_distribution
```

Рейтинговый подбор учитывает сезон, blocklist, калибровку и Elo. Начальный диапазон
по умолчанию составляет `±100 Elo`, расширяется каждые пять минут на `50 Elo` и
ограничивается `±400 Elo`. Обычная `/queue` не смешивается с рейтинговой.

После пяти матчей открывается один из семи дивизионов: Бронза, Серебро, Золото,
Платина, Алмаз, Мастер или Грандмастер.

## 🎯 Персональные вызовы

```text
/challenge тема
/challenge USER_ID тема
/challenges
/accept_challenge ID
/decline_challenge ID
/cancel_challenge ID
```

Вызовы хранятся в PostgreSQL, переживают перезапуск и используют состояние
`accepting`, защищающее от двойного запуска матча.

## ⚔️ Основные PvP-команды

| Команда | Назначение |
|---|---|
| `/duel [тема]` | Открытое приглашение |
| `/queue [тема]` | Обычная очередь |
| `/ranked_queue [тема]` | Рейтинговая очередь по Elo |
| `/duel_status` | Активная дуэль |
| `/cancel_duel` | Отменить до первого хода |
| `/forfeit` | Сдаться |
| `/rating` | Elo и место |
| `/pvp_leaderboard` | Топ-10 текущего сезона |
| `/duel_history` | История матчей |
| `/pvp_stats` | Расширенная аналитика |
| `/rivals` | Главные соперники |
| `/head_to_head USER_ID` | Личные встречи |
| `/pvp_profile [USER_ID]` | PvP-карточка |

## 🎁 Прогресс и косметика

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

Ranked rewards и daily-награды используют существующий progression wallet. Косметика
не влияет на Elo, подбор или судейство.

## 🔐 Приватность и безопасность

```text
/profile_visibility public|private
/block USER_ID
/unblock USER_ID
/blocked
/report категория комментарий
/my_reports
/privacy
/delete_me
```

Сезонные цели приватны. В `pvp_season_goals` сохраняются только user ID, сезон,
фиксированный metric ID, baseline, target и timestamps. Свободный текст отсутствует.

Публичность PvP-профиля выключена по умолчанию. Баланс токенов, coaching, recaps,
career records, reward claims и цели другим игрокам не показываются. Blocklist
применяется к приглашениям, очередям, вызовам, рематчам и чужому профилю.

`/delete_me` удаляет цели явно, а внешний ключ таблицы дополнительно использует
`ON DELETE CASCADE`.

## 🧠 Надёжность v0.17

- неизвестные метрики и некорректные диапазоны отклоняются;
- цель нельзя создать, когда она уже выполнена с достаточной выборкой;
- win rate требует минимум 5 матчей;
- skill goals требуют минимум 3 корректных score payload;
- повреждённые оценки пропускаются без падения остальных метрик;
- progress всегда ограничен диапазоном 0–100%;
- completion timestamp сохраняется после регрессии;
- одновременно разрешено не более 5 активных целей;
- рекомендации исключают уже активные метрики;
- новых runtime-зависимостей и фоновых задач нет.

## 🗄️ Хранилища

### PostgreSQL

Профили, архивы, сезонный Elo, завершённые матчи и оценки, blocklist, жалобы,
progression, daily claims, косметика, публичность, вызовы, ranked reward claims и
приватные сезонные цели.

### Redis

Активные споры и PvP-матчи, приглашения, обычная и рейтинговая очереди, временные
Elo-снимки, дедлайны, request locks, rate limit и подтверждения удаления данных.

## ⚙️ Настройки

```env
PVP_SEASON=season-1
PVP_COACH_WINDOW_MATCHES=10
PVP_RANKED_BASE_ELO_GAP=100
PVP_RANKED_ELO_GAP_STEP=50
PVP_RANKED_EXPAND_INTERVAL_SECONDS=300
PVP_RANKED_MAX_ELO_GAP=400
PVP_CHALLENGE_TTL_HOURS=24
```

## 🚀 Установка и запуск

```bash
git clone https://github.com/Onmaynec/DisputesBot.git
cd DisputesBot
cp .env.example .env
docker compose up -d postgres redis
pip install -e ".[dev]"
alembic upgrade head
python -m bot.main
```

Полный Docker-запуск:

```bash
docker compose up --build -d
```

## ⬆️ Обновление с v0.16

```bash
git pull
pip install -e ".[dev]"
alembic upgrade head
```

Миграция `0009_season_goals` добавляет одну приватную таблицу целей и индекс по
пользователю, сезону и завершению. Существующие Elo, матчи, награды, архивы и вызовы
не изменяются.

## 🧪 Проверки

```bash
ruff check .
python -m compileall -q bot tests migrations
alembic upgrade head
pytest -q
```

GitHub Actions проверяет Python 3.11 и 3.13 с PostgreSQL 17.

## 📦 Релизы

После push в `main` workflow `.github/workflows/release.yml` читает версию из
`pyproject.toml`, собирает wheel и source distribution, создаёт тег `vX.Y.Z` и
публикует GitHub Release.

## 📄 Лицензия

MIT
