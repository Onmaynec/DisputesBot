<div align="center">

# ⚔️ DisputesBot v0.6

**Telegram-бот для тренировки дебатов, логики и критического мышления**

![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![aiogram](https://img.shields.io/badge/aiogram-3.30.0-2CA5E0)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-profiles%20%26%20moderation-336791)
![Redis](https://img.shields.io/badge/Redis-live%20PvP-red)
![Version](https://img.shields.io/badge/version-0.6.0-brightgreen)

</div>

## ✨ Новое в v0.6

- 🚫 постоянный PvP-блок-лист: `/block`, `/unblock`, `/blocked`;
- 🛡 структурированные жалобы: `/report` и `/my_reports`;
- ⌛ дедлайн каждого хода и автоматическое завершение зависших матчей;
- 🔁 `/rematch_duel` для персонального приглашения последнего соперника;
- 🧯 защита Elo от повторного фарминга одной парой;
- 🧑‍⚖️ служебная очередь жалоб с аудитом решений;
- 🩺 агрегированная PvP-диагностика без раскрытия стенограмм;
- 🧱 Alembic-миграция `0003_moderation`.

PvP v0.5, одиночные споры, турниры, достижения, приватность и Markdown-экспорт сохранены.

## 🎮 Команды

### PvP

| Команда | Назначение |
|---|---|
| `/duel [тема]` | Создать открытое приглашение в дуэль |
| `/queue [тема]` | Встать в очередь автоматического подбора |
| `/leave_queue` | Выйти из очереди |
| `/rematch_duel [тема]` | Отправить персональный рематч последнему сопернику |
| `/duel_status` | Позиции, прогресс, текущий ход и дедлайн |
| `/cancel_duel` | Отменить матч до первого аргумента без Elo |
| `/forfeit` | Сдаться после начала матча |
| `/rating` | Личный Elo и место в сезоне |
| `/pvp_leaderboard` | Топ-10 игроков сезона |
| `/duel_history` | Последние пять PvP-матчей |

### Безопасность и жалобы

| Команда | Назначение |
|---|---|
| `/block` | Заблокировать пользователя ответом на сообщение |
| `/block user_id` | Заблокировать пользователя по Telegram ID |
| `/unblock user_id` | Удалить пользователя из блок-листа |
| `/blocked` | Показать блок-лист |
| `/report категория комментарий` | Пожаловаться на активный или последний матч |
| `/my_reports` | Посмотреть свои жалобы и статусы |

Категории жалоб: `оскорбления`, `спам`, `обход_правил`, `другое`.

### Одиночные режимы

| Команда | Назначение |
|---|---|
| `/debate [тема]` | Начать обычный спор с ботом |
| `/role [роль]` | Изменить стиль оппонента |
| `/difficulty [уровень]` | Выбрать сложность |
| `/summary` | Получить резюме тезисов |
| `/judge` | Запустить независимое судейство |
| `/fallacies` | Найти логические ошибки |
| `/tournament` | Турнир из трёх раундов |
| `/history [1-10]` | История сохранённых споров |
| `/rematch` | Повторить последнюю одиночную тему |
| `/export [current\|last\|N]` | Выгрузить спор в Markdown |
| `/stats` | Статистика и прогресс |
| `/achievements` | Достижения |
| `/leaderboard` | Лидерборд одиночных турниров |
| `/privacy` | Политика хранения данных |
| `/delete_me` | Удалить персональные данные |
| `/cancel` | Завершить одиночный спор |

## ⚔️ Как проходит PvP-дуэль

1. Пользователь создаёт `/duel [тема]`, `/rematch_duel` или входит в `/queue`.
2. Blocklist-политика проверяется в обе стороны до создания матча.
3. Позиции «за» и «против» назначаются случайно и фиксируются.
4. Сторона «за» делает первый ход; дальше ходы строго чередуются.
5. После каждого аргумента Redis сохраняет новый дедлайн следующего участника.
6. После шестого аргумента независимый судья получает анонимных участников A/B.
7. PostgreSQL транзакционно сохраняет один результат по `match_id`.
8. При повторной записи `match_id` рейтинг не начисляется второй раз.

## ⌛ Дедлайны и восстановление

`PVP_TURN_TIMEOUT_SECONDS` задаёт время одного хода. По умолчанию — 3600 секунд.

- до первого аргумента timeout отменяет матч без изменения Elo;
- после начала timeout считается поражением участника, чей ход истёк;
- каждый принятый аргумент продлевает дедлайн;
- background sweep использует отдельный match-lock;
- повторный sweep не может записать результат дважды;
- `/duel_status` показывает приблизительно оставшееся время.

Активный матч, дедлайн и индексы участников восстанавливаются из Redis после перезапуска.

## 🏅 Elo и защита от фарминга

- стартовый рейтинг: **1000 Elo**;
- коэффициент: **K=32**;
- изменения двух игроков симметричны и дают нулевую сумму;
- текущий сезон задаётся `PVP_SEASON`;
- одна пара может провести ограниченное число рейтинговых матчей за временное окно;
- последующие матчи сохраняются в истории и статистике, но имеют нулевые Elo-дельты.

Настройки:

```dotenv
PVP_REPEAT_WINDOW_SECONDS=86400
PVP_MAX_RATED_PAIR_MATCHES=3
```

Смена сторон не обходит лимит: пара определяется по отсортированным Telegram user_id.

## 🚫 Blocklist

Блокировка направленная, но применяется к подбору симметрично: если хотя бы один участник заблокировал другого, новая дуэль этой пары невозможна.

При `/block` бот также удаляет ожидающее приглашение и запись автора блокировки из очереди. Активный матч автоматически не прерывается: его можно штатно завершить или использовать `/forfeit`.

## 🛡 Жалобы и служебная модерация

Жалоба содержит:

- стабильный `report_id`;
- `match_id` и тему матча;
- категорию и комментарий до 500 символов;
- статус `open`, `resolved` или `rejected`;
- moderator user_id, заметку и время решения.

Один пользователь создаёт не более одной жалобы на один матч. Жалоба не меняет исход или Elo.

Служебные команды доступны только ID из `MODERATOR_USER_IDS`:

```text
/admin_reports [open|resolved|rejected]
/resolve_report report_id [resolved|rejected] [заметка]
/pvp_health
```

`/pvp_health` показывает только агрегаты: число активных матчей, размер очереди и открытые жалобы. Тексты аргументов не выводятся.

## 🗄 Архитектура хранения

**Redis**:

- активные одиночные споры;
- живые PvP-матчи и дедлайны;
- индекс пользователь → матч;
- множество активных `match_id` для timeout sweep;
- приглашения и очередь;
- request locks и rate limiting.

**PostgreSQL**:

- пользовательские профили и одиночная статистика;
- архивы одиночных споров;
- сезонный PvP Elo;
- завершённые PvP-матчи и признак `rated`;
- направленные пользовательские блокировки;
- жалобы и аудит решений.

`/delete_me` удаляет профиль, историю, рейтинг, blocklist и Redis-состояние. Жалоба остаётся аудиторской записью, но `reporter_id` очищается.

## 🚀 Запуск через Docker Compose

```bash
git clone https://github.com/Onmaynec/DisputesBot.git
cd DisputesBot
cp .env.example .env
```

Минимальная конфигурация:

```dotenv
BOT_TOKEN=telegram_bot_token
OPENAI_API_KEY=openai_api_key
DATABASE_URL=postgresql+asyncpg://disputesbot:disputesbot@postgres:5432/disputesbot
REDIS_URL=redis://redis:6379/0
PVP_SEASON=season-1
MODERATOR_USER_IDS=123456789
```

Запуск:

```bash
docker compose up -d --build
```

Контейнер дождётся Redis и PostgreSQL, выполнит `alembic upgrade head`, затем запустит polling и timeout-sweeper.

## 🧰 Локальный запуск

```bash
python -m venv .venv
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

```bash
pip install -e ".[dev]"
alembic upgrade head
python -m bot.main
```

## ⬆️ Обновление с v0.5

1. Создайте резервную копию PostgreSQL и Redis.
2. Обновите код и новые переменные `.env`.
3. Примените миграции:

```bash
docker compose run --rm disputes-bot alembic upgrade head
```

Цепочка должна завершиться так:

```text
0001_profiles → 0002_pvp → 0003_moderation
```

4. Перезапустите стек:

```bash
docker compose up -d --build
```

`0003_moderation` добавляет blocklist, reports и метаданные рейтингового режима. Старые профили, архивы и матчи не удаляются; для старых PvP-матчей вычисляется `pair_key`.

## 🧹 Обслуживание Redis

Штатно используйте `/duel_status`, `/forfeit` и `/cancel_duel`. Timeout-sweeper автоматически очищает просроченные матчи.

Основные ключи:

```text
<REDIS_PREFIX>:pvp:match:<match_id>
<REDIS_PREFIX>:pvp:user:<telegram_user_id>
<REDIS_PREFIX>:pvp:active
<REDIS_PREFIX>:pvp:queue
```

Удаление только ключа матча без пользовательских индексов не рекомендуется. Store самостоятельно очищает найденные stale-индексы при чтении.

## 💾 Резервное копирование

```bash
docker compose exec postgres pg_dump \
  -U disputesbot -d disputesbot -Fc -f /tmp/disputesbot.dump
docker compose cp postgres:/tmp/disputesbot.dump ./disputesbot.dump
```

Восстановление:

```bash
docker compose cp ./disputesbot.dump postgres:/tmp/disputesbot.dump
docker compose exec postgres pg_restore \
  -U disputesbot -d disputesbot --clean --if-exists /tmp/disputesbot.dump
```

## 🧪 Проверки

```bash
ruff check .
python -m compileall -q bot tests migrations
pytest -q
alembic upgrade head
```

GitHub Actions запускает полный набор на Python 3.11 и 3.13 с PostgreSQL 17.

## 📁 Основные модули

```text
bot/pvp_models.py              PvP-состояния, дедлайны и timeout
bot/pvp_store.py               Redis-матчи, очередь, active set и locks
bot/pvp_repository.py          Elo, anti-farm и история
bot/moderation_repository.py   blocklist, reports и аудит
bot/moderation_commands.py     пользовательские и служебные команды
bot/pvp_rematch.py             персональный рематч
bot/pvp_timeout.py             фоновая финализация дедлайнов
migrations/versions/0003_*     схема v0.6
```

## 📄 Лицензия

MIT — см. [LICENSE](LICENSE).
