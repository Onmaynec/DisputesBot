<div align="center">

# ⚔️ DisputesBot v0.7

**Telegram-бот для тренировки дебатов, логики и критического мышления**

![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![aiogram](https://img.shields.io/badge/aiogram-3.30.0-2CA5E0)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Elo%20%26%20progression-336791)
![Redis](https://img.shields.io/badge/Redis-live%20sessions-red)
![Version](https://img.shields.io/badge/version-0.7.0-brightgreen)

</div>

## ✨ Новое в v0.7

- 🎯 три ежедневных PvP-задания через `/daily`;
- 🎁 безопасное получение всех готовых наград командой `/daily_claim`;
- 🪙 отдельные PvP-токены и ⭐ сезонные очки;
- 🔥 текущая и лучшая серия дней с полученными наградами;
- 🏅 шесть уровней сезонного прогресса через `/season`;
- 🏆 отдельный лидерборд прогресса `/season_top`;
- 📊 расширенная аналитика `/pvp_stats`;
- 🧱 Alembic-миграция `0004_progression`.

Все возможности v0.6 сохранены: рейтинговый PvP, рематчи, дедлайны, blocklist,
жалобы, moderator audit, одиночные споры, турниры и экспорт.

## 🎯 Ежедневные задания

Каждый progression-день бот детерминированно выбирает три задания из каталога:

- завершить один или два PvP-матча;
- победить в PvP;
- завершить два рейтинговых матча;
- сыграть с двумя разными соперниками;
- победить в рейтинговом матче.

Задания не хранятся в scheduler и не меняются после перезапуска. Набор вычисляется
по календарной дате, а прогресс — по неизменяемой истории завершённых матчей.

```text
/daily        показать задания, прогресс и награды
/daily_claim  получить все завершённые неполученные награды
```

Повторный `/daily_claim` не начисляет награду второй раз. Уникальный ключ claim:
`user_id + season + day + quest_id`.

## 🏅 Сезонный прогресс

Сезонные очки существуют отдельно от Elo и не влияют на подбор или рейтинг.

| Уровень | Название | Минимум очков |
|---:|---|---:|
| 1 | Новичок | 0 |
| 2 | Спорщик | 100 |
| 3 | Оратор | 250 |
| 4 | Тактик | 450 |
| 5 | Мастер аргумента | 700 |
| 6 | Легенда сезона | 1000 |

```text
/season      токены, очки, уровень и серии
/season_top  топ-10 по очкам текущего сезона
```

При равных очках сортировка учитывает токены, время обновления и user ID, поэтому
лидерборд остаётся стабильным.

## 📊 PvP-аналитика

Команда `/pvp_stats` показывает:

- текущий Elo и место в сезоне;
- общее число матчей;
- рейтинговые и нерейтинговые матчи отдельно;
- победы, ничьи, поражения и win rate;
- число уникальных соперников;
- изменение Elo за настраиваемое окно;
- текущую и лучшую серию побед;
- результаты отдельно за стороны «за» и «против».

## 🎮 Основные команды

### PvP

| Команда | Назначение |
|---|---|
| `/duel [тема]` | Создать открытое PvP-приглашение |
| `/queue [тема]` | Встать в очередь автоматического подбора |
| `/leave_queue` | Выйти из очереди |
| `/rematch_duel [тема]` | Пригласить последнего соперника |
| `/duel_status` | Показать ход, прогресс и дедлайн |
| `/cancel_duel` | Отменить матч до первого аргумента |
| `/forfeit` | Сдаться после начала матча |
| `/rating` | Личный Elo и место |
| `/pvp_leaderboard` | Топ-10 по Elo |
| `/duel_history` | История PvP-матчей |
| `/pvp_stats` | Расширенная аналитика |
| `/daily` | Ежедневные задания |
| `/daily_claim` | Получить награды |
| `/season` | Сезонный прогресс |
| `/season_top` | Топ по сезонным очкам |

### Безопасность

| Команда | Назначение |
|---|---|
| `/block` | Заблокировать пользователя ответом на сообщение |
| `/block user_id` | Заблокировать пользователя по Telegram ID |
| `/unblock user_id` | Удалить пользователя из blocklist |
| `/blocked` | Показать blocklist |
| `/report категория комментарий` | Пожаловаться на матч |
| `/my_reports` | Показать свои жалобы |

### Одиночные режимы

`/debate`, `/role`, `/difficulty`, `/summary`, `/judge`, `/fallacies`, `/tournament`,
`/history`, `/rematch`, `/export`, `/stats`, `/achievements`, `/leaderboard`,
`/privacy`, `/delete_me`, `/cancel`.

## 🧠 Надёжность progression

- набор заданий определяется функцией от даты;
- прогресс читается из PostgreSQL-истории матчей;
- claim выполняется одной транзакцией;
- профиль игрока блокируется перед начислением;
- составной primary key исключает повторное получение;
- серия дня изменяется только при первом успешном claim этого дня;
- награды не вызывают OpenAI-запросов и не меняют Elo.

## 🗄️ Хранилища

### PostgreSQL

Постоянно хранятся профили, архивы, PvP Elo, завершённые матчи, blocklist,
жалобы, progression wallets и история полученных заданий.

### Redis

Временно хранятся активные споры, PvP-матчи, приглашения, очередь, дедлайны,
request locks, rate limit и подтверждение удаления данных.

## ⚙️ Переменные v0.7

```env
PVP_DAILY_RESET_HOUR_UTC=0
PVP_DAILY_REWARD_MULTIPLIER=1
PVP_STATS_WINDOW_DAYS=30
```

Ограничения:

- reset hour: `0..23`;
- reward multiplier: `1..10`;
- analytics window: `1..365` дней.

Остальные переменные перечислены в `.env.example`.

## 🚀 Запуск

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

Полный запуск в Docker:

```bash
docker compose up --build -d
```

## ⬆️ Обновление с v0.6

```bash
git pull
pip install -e ".[dev]"
alembic upgrade head
```

Миграция `0004_progression` добавляет только:

- `pvp_progression`;
- `pvp_daily_claims`;
- индексы сезонного прогресса и claims.

Существующие профили, PvP-матчи, Elo, blocklist и жалобы не изменяются.

## 🧪 Проверки

```bash
ruff check .
python -m compileall -q bot tests migrations
alembic upgrade head
pytest -q
```

GitHub Actions запускает проверки с PostgreSQL 17 на Python 3.11 и 3.13.

## 🔐 Приватность

`/delete_me` удаляет профиль, архивы, PvP-рейтинг, историю матчей, blocklist,
progression wallet, daily claims, настройки и активные Redis-сессии. Жалобы остаются
как обезличенные аудиторские записи.

## 📄 Лицензия

MIT.
