<div align="center">

# ⚔️ DisputesBot v0.15

**Telegram-бот для тренировки дебатов, логики и критического мышления**

![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![aiogram](https://img.shields.io/badge/aiogram-3.30.0-2CA5E0)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-rewards%20%26%20archives-336791)
![Redis](https://img.shields.io/badge/Redis-ranked%20matchmaking-red)
![Version](https://img.shields.io/badge/version-0.15.0-brightgreen)

</div>

## ✨ Новое в v0.15

- 🗂 `/pvp_career` — личная карьера по всем сохранённым PvP-сезонам;
- 📈 финальный Elo, стартовый Elo, изменение и карьерный пик каждого сезона;
- 🏆 `/season_archive [season]` — историческая таблица выбранного сезона;
- 👑 `/hall_of_fame` — чемпион каждого сохранённого сезона;
- 🧭 дивизион и место восстанавливаются по тем же правилам, что live leaderboard;
- ♻️ архив вычисляется из существующих данных без новой таблицы и миграции.

Все возможности v0.14 сохранены: claimable ranked rewards, миграция
`0008_ranked_rewards`, приватный coaching, Elo-aware matchmaking, вызовы и косметика.

## 🗂 Карьера и сезонный архив

```text
/pvp_career
/season_archive
/season_archive season-1
/hall_of_fame
```

`/pvp_career` показывает число сезонов и матчей, общий рекорд, процент побед,
карьерный максимум Elo, лучший сезон и до десяти сезонных строк с итоговым Elo,
пиковым Elo, изменением рейтинга, местом и рекордом.

Пиковый Elo восстанавливается из сохранённых значений `rating_before` и
`rating_after` каждого матча. Отдельный карьерный профиль не создаётся.

`/season_archive` без аргумента выводит доступные сезоны, число игроков и матчей.
С аргументом показывает топ-10 выбранного сезона. Активный сезон помечается отдельно.

`/hall_of_fame` показывает лидера каждого сезона. Чемпион определяется стабильным
порядком: Elo, число матчей, время обновления и Telegram user ID.

Архивные команды не читают стенограммы, аргументы или judge score payload. Они
используют только сезонные строки Elo, публичное отображаемое имя и агрегаты матчей.

## 🎁 Награды рейтинговых лиг

После завершения пяти калибровочных матчей игрок может забрать все награды до
максимального достигнутого Elo сезона. Падение рейтинга не отменяет заработанную
награду.

| Дивизион | Минимальный Elo | Награда |
|---|---:|---:|
| 🥉 Бронза | 0 | 15 🪙 |
| 🥈 Серебро | 900 | 25 🪙 |
| 🥇 Золото | 1000 | 40 🪙 |
| 💠 Платина | 1100 | 60 🪙 |
| 💎 Алмаз | 1200 | 90 🪙 |
| 🏅 Мастер | 1300 | 130 🪙 |
| 👑 Грандмастер | 1450 | 200 🪙 |

```text
/ranked_rewards
/claim_ranked_rewards
```

Claim выполняется одной PostgreSQL-транзакцией. Составной ключ
`(user_id, season, league_id)` исключает повторное начисление. Токены не меняют Elo,
season points, matchmaking, судейство или результат матча.

## 🎓 Приватный PvP coaching

```text
/match_review
/match_review MATCH_ID
/pvp_coach
```

`/match_review` показывает приватный разбор собственного оценённого матча: позицию,
результат, Elo-дельту, logic, evidence, rebuttal, сравнение с соперником и сохранённый
вердикт. Чужой матч невозможно открыть подбором ID.

`/pvp_coach` агрегирует последние оценённые матчи текущего сезона, показывает средние
навыки, результаты, тренд, сильную сторону и фокус тренировки. Новых OpenAI-запросов
для отчёта нет.

## 🎯 Рейтинговый matchmaking

```text
/ranked_queue Искусственный интеллект полезен обществу
/queue_status
/leave_queue
```

Начальный диапазон составляет `±100 Elo`, каждые пять минут расширяется на `50 Elo`
и ограничивается `±400 Elo`. Калибровочные игроки подбираются только с
калибровочными, обычная `/queue` не смешивается с рейтинговой.

Подбор учитывает сезон, blocklist, занятость, placement и Elo. Среди подходящих
кандидатов выбирается минимальная разница Elo, затем время ожидания и user ID.

## 🏆 Рейтинговые лиги

Первые пять завершённых PvP-матчей считаются калибровочными. Elo изменяется сразу,
но дивизион и ranked rewards открываются после placement.

```text
/league               дивизион, место, форма и прогресс
/league_top           топ-10 текущего сезона
/league_distribution  распределение игроков
```

Лиги вычисляются из существующих агрегатов Elo и отдельно не сохраняются.

## 🎯 Персональные PvP-вызовы

```text
/challenge тема                         reply на сообщение соперника
/challenge 123456789 тема               вызвать известного пользователя
/challenges                             входящие и исходящие вызовы
/accept_challenge ID                    принять вызов
/decline_challenge ID                   отклонить вызов
/cancel_challenge ID                    отменить свой вызов
```

Вызовы хранятся в PostgreSQL, переживают перезапуск и используют состояние
`accepting`, защищающее от двойного запуска матча.

## ⚔️ Основные PvP-команды

| Команда | Назначение |
|---|---|
| `/duel [тема]` | Открытое приглашение |
| `/queue [тема]` | Обычная очередь |
| `/ranked_queue [тема]` | Рейтинговая очередь по Elo |
| `/queue_status` | Режим и диапазон поиска |
| `/leave_queue` | Выйти из очереди |
| `/duel_status` | Состояние активной дуэли |
| `/cancel_duel` | Отменить матч до первого хода |
| `/forfeit` | Сдаться |
| `/rating` | Elo и место |
| `/league` | Дивизион и прогресс |
| `/ranked_rewards` | Награды лиг |
| `/claim_ranked_rewards` | Получить токены лиг |
| `/pvp_career` | Карьера по сезонам |
| `/season_archive [сезон]` | Список или таблица сезона |
| `/hall_of_fame` | Чемпионы сезонов |
| `/pvp_leaderboard` | Топ-10 текущего сезона |
| `/duel_history` | История матчей |
| `/pvp_stats` | Расширенная аналитика |
| `/match_review [ID]` | Приватный разбор матча |
| `/pvp_coach` | Тренд PvP-навыков |
| `/rivals` | Главные соперники |
| `/head_to_head user_id` | Личные встречи |

## 🎁 Прогресс и косметика

```text
/daily                 ежедневные PvP-задания
/daily_claim           получить награды заданий
/season                токены, очки и серии
/season_top            лидерборд прогресса
/shop                   каталог косметики
/buy ITEM_ID            купить предмет
/inventory              инвентарь
/equip ITEM_ID          экипировать предмет
/unequip title|badge    снять предмет
```

Ranked rewards добавляют токены в существующий progression wallet. Косметика и награды
не влияют на Elo, matchmaking, судейство или исход матча.

## 🔐 Профили и безопасность

```text
/pvp_profile [user_id]
/profile_visibility public|private
/block user_id
/unblock user_id
/blocked
/report категория комментарий
/my_reports
```

Публичность профиля выключена по умолчанию. Баланс токенов, coaching-отчёты и история
ranked reward claims не показываются другим игрокам. Blocklist применяется к
приглашениям, очередям, вызовам, рематчам и просмотру чужого профиля.

## 🧠 Надёжность season archive

- личная карьера читает только строки и матчи запрашивающего пользователя;
- пик Elo восстанавливается из `rating_before` и `rating_after`;
- архивная таблица использует те же tie-breakers, что live leaderboard;
- сезоны упорядочиваются по последней активности;
- неизвестные и слишком длинные season ID безопасно отклоняются;
- размер каталогов и таблиц ограничен;
- архив не дублирует данные и не может рассинхронизироваться с Elo;
- новых OpenAI-запросов, фоновых задач и runtime-зависимостей нет.

## 🗄️ Хранилища

### PostgreSQL

Профили, архивы, сезонный Elo, завершённые матчи и судейские оценки, blocklist,
жалобы, progression wallets, daily claims, косметика, публичность профиля,
персональные вызовы и журнал ranked reward claims.

`pvp_ranked_reward_claims` хранит только user ID, сезон, ID дивизиона, число токенов,
Elo при claim и время операции. Карьера и сезонный архив отдельно не сохраняются.

### Redis

Активные споры и PvP-матчи, приглашения, обычная и рейтинговая очереди, временные
Elo-снимки, дедлайны, request locks, rate limit и подтверждения удаления данных.

## ⚙️ Настройки PvP

```env
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

## ⬆️ Обновление с v0.14

```bash
git pull
pip install -e ".[dev]"
alembic upgrade head
```

v0.15 не меняет PostgreSQL-схему. Последняя миграция остаётся
`0008_ranked_rewards`. Существующие Elo, матчи, награды, кошельки и вызовы не
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

`/pvp_career` показывает только собственную карьеру. Исторические таблицы используют
те же публичные агрегаты, что текущий PvP-лидерборд, и не раскрывают аргументы,
стенограммы или судейские баллы.

`/delete_me` удаляет профиль, архивы, PvP-рейтинг, матчи и coaching-источник,
progression wallet, daily claims, ranked reward claims, косметику, публичность,
вызовы, blocklist, обе очереди и активные Redis-сессии. После удаления пользователь
исчезает из карьерных и сезонных представлений. Жалобы остаются обезличенными.

## 📄 Лицензия

MIT
