<div align="center">

# ⚔️ DisputesBot v0.16

**Telegram-бот для тренировки дебатов, логики и критического мышления**

![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![aiogram](https://img.shields.io/badge/aiogram-3.30.0-2CA5E0)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-season%20insights-336791)
![Redis](https://img.shields.io/badge/Redis-ranked%20matchmaking-red)
![Version](https://img.shields.io/badge/version-0.16.0-brightgreen)

</div>

## ✨ Новое в v0.16

- 📊 `/season_recap [season]` — подробные личные итоги PvP-сезона;
- ⚖️ `/compare_seasons [старый новый]` — сравнение двух сезонов;
- 🏅 `/career_records` — личные рекорды за всю PvP-карьеру;
- 📈 стартовый, итоговый и пиковый Elo, прирост и историческое место;
- 🔥 лучшая серия побед, rated/unrated-матчи и уникальные соперники;
- 🧠 средние logic, evidence и rebuttal за весь сезон;
- 🎁 число полученных ranked milestones и заработанных токенов;
- ♻️ отчёты вычисляются из существующих данных без новой таблицы и миграции.

Все возможности v0.15 сохранены: сезонный архив, Hall of Fame, ranked rewards,
приватный coaching, Elo-aware matchmaking, персональные вызовы и косметика.

## 📊 Персональные итоги сезона

```text
/season_recap
/season_recap season-1
```

Без аргумента используется текущий `PVP_SEASON`. Команда показывает:

- дивизион или оставшиеся калибровочные матчи;
- стартовый, итоговый и пиковый Elo;
- прирост рейтинга и место среди всех игроков сезона;
- победы, ничьи, поражения и win rate;
- rated/unrated-матчи и число уникальных соперников;
- максимальную серию побед;
- самого частого соперника;
- средние судейские оценки logic, evidence и rebuttal;
- сильную сторону и текущий фокус тренировки;
- полученные ranked reward milestones и токены.

Recap доступен только владельцу Telegram user ID. Отдельный recap-профиль не
сохраняется, а OpenAI повторно не вызывается.

## ⚖️ Сравнение сезонов

```text
/compare_seasons
/compare_seasons season-1 season-2
```

Без аргументов сравниваются два последних сезона игрока. Сравнение показывает
изменение итогового и пикового Elo, win rate, числа матчей, максимальной серии побед
и среднего судейского балла.

Неизвестные, одинаковые, слишком длинные или содержащие пробелы season ID безопасно
отклоняются.

## 🏅 Карьерные рекорды

```text
/career_records
```

Команда выбирает рекордные сезоны по следующим показателям:

- высший итоговый Elo;
- абсолютный пик Elo;
- максимальное число побед;
- максимальное число матчей;
- лучший win rate;
- наибольший прирост Elo;
- самая длинная серия побед.

Для рекорда win rate приоритет получают сезоны минимум с пятью матчами. Для короткой
карьеры используется безопасный fallback на доступные сезоны.

## 🗂 Карьера и сезонный архив

```text
/pvp_career
/season_archive
/season_archive season-1
/hall_of_fame
```

`/pvp_career` показывает карьеру игрока по всем сохранённым сезонам. Пиковый Elo
восстанавливается из сохранённых `rating_before` и `rating_after`.

`/season_archive` без аргумента выводит каталог сезонов, а с season ID — исторический
топ-10. `/hall_of_fame` показывает чемпиона каждого сезона. Архивные таблицы используют
те же стабильные tie-breakers, что текущий лидерборд: Elo, число матчей, время
обновления и user ID.

## 🎁 Награды рейтинговых лиг

```text
/ranked_rewards
/claim_ranked_rewards
```

После пяти калибровочных матчей игрок может забрать накопительные награды до
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
/match_review
/match_review MATCH_ID
/pvp_coach
```

`/match_review` показывает приватный разбор собственного оценённого матча.
`/pvp_coach` агрегирует последние оценённые матчи текущего сезона, показывает тренд,
сильную сторону и фокус тренировки. Оба отчёта используют сохранённые score payload и
не создают новых OpenAI-запросов.

## 🎯 Рейтинговый matchmaking

```text
/ranked_queue тема
/queue_status
/leave_queue
```

Начальный диапазон составляет `±100 Elo`, каждые пять минут расширяется на `50 Elo`
и ограничивается `±400 Elo`. Калибровочные игроки подбираются только с
калибровочными, а обычная `/queue` не смешивается с рейтинговой.

## 🏆 Рейтинговые лиги

```text
/league
/league_top
/league_distribution
```

Первые пять завершённых PvP-матчей считаются калибровочными. После калибровки игрок
получает один из семи дивизионов: Бронза, Серебро, Золото, Платина, Алмаз, Мастер или
Грандмастер.

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
| `/duel_status` | Состояние активной дуэли |
| `/cancel_duel` | Отменить матч до первого хода |
| `/forfeit` | Сдаться |
| `/rating` | Elo и место |
| `/pvp_leaderboard` | Топ-10 текущего сезона |
| `/duel_history` | История матчей |
| `/pvp_stats` | Расширенная аналитика |
| `/rivals` | Главные соперники |
| `/head_to_head USER_ID` | Личные встречи |
| `/pvp_profile [USER_ID]` | Своя или публичная PvP-карточка |

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

Ranked rewards и daily-награды добавляют токены в существующий progression wallet.
Косметика не влияет на Elo, matchmaking, судейство или исход матча.

## 🔐 Профили и безопасность

```text
/profile_visibility public|private
/block USER_ID
/unblock USER_ID
/blocked
/report категория комментарий
/my_reports
```

Публичность профиля выключена по умолчанию. Баланс токенов, coaching, season recap,
comparison, career records и история reward claims не показываются другим игрокам.
Blocklist применяется к приглашениям, очередям, вызовам, рематчам и просмотру профиля.

## 🧠 Надёжность v0.16

- recap читает только `pvp_players`, матчи пользователя и его reward claims;
- Elo-путь учитывает final player row и все before/after значения;
- серия побед вычисляется в хронологическом порядке;
- ничья или поражение сбрасывает текущую серию;
- повреждённые score payload пропускаются;
- favorite-opponent tie-break детерминирован по user ID;
- сравнение двух последних сезонов основано на `updated_at`;
- все сезонные выборки ограничены 20 сезонами по умолчанию;
- новых таблиц, миграций, зависимостей и фоновых задач нет.

## 🗄️ Хранилища

### PostgreSQL

Профили, архивы, сезонный Elo, завершённые матчи и оценки, blocklist, жалобы,
progression wallets, daily claims, косметика, публичность профиля, вызовы и журнал
ranked reward claims.

Season recap, сравнения и карьерные рекорды отдельно не сохраняются.

### Redis

Активные споры и PvP-матчи, приглашения, обычная и рейтинговая очереди, временные
Elo-снимки, дедлайны, request locks, rate limit и подтверждения удаления данных.

## ⚙️ Настройки PvP

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
```

Заполните `BOT_TOKEN`, `OPENAI_API_KEY` и при необходимости `MODERATOR_USER_IDS`.

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

## ⬆️ Обновление с v0.15

```bash
git pull
pip install -e ".[dev]"
alembic upgrade head
```

v0.16 не меняет PostgreSQL-схему. Последняя миграция остаётся
`0008_ranked_rewards`. Существующие Elo, матчи, награды, кошельки, архивы и вызовы не
изменяются.

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
`pyproject.toml`, собирает wheel и source distribution, извлекает notes из
`CHANGELOG.md`, создаёт тег `vX.Y.Z` и публикует GitHub Release.

## 🔐 Удаление данных

`/delete_me` удаляет профиль, PvP-рейтинг, матчи и оценки, progression wallet, daily
claims, ranked reward claims, косметику, публичность, вызовы, blocklist, очереди и
активные Redis-сессии. После удаления исчезают recap, сравнения, личные рекорды,
карьерные и сезонные представления. Жалобы остаются обезличенными аудиторскими
записями.

## 📄 Лицензия

MIT
