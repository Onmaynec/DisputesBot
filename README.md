<div align="center">

# ⚔️ DisputesBot v0.4

**Telegram-бот для тренировки дебатов, логики и критического мышления**

![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![aiogram](https://img.shields.io/badge/aiogram-3.30.0-2CA5E0)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-profiles-336791)
![Redis](https://img.shields.io/badge/Redis-sessions-red)
![Version](https://img.shields.io/badge/version-0.4.0-brightgreen)

</div>

## ✨ Новое в v0.4

- 🐘 постоянные профили, статистика и история перенесены в PostgreSQL;
- 🧱 Alembic управляет схемой базы данных;
- 📥 импорт старого `data/leaderboard.json` версий 0.2–0.3;
- 🔐 `/privacy` объясняет, какие данные сохраняются;
- 🗑 `/delete_me` удаляет PostgreSQL-профиль и Redis-данные после подтверждения;
- 📄 `/export` выгружает текущий или архивный спор в Markdown;
- 🔁 транзакционные и идемпотентные обновления по `session_id`;
- 🧪 PostgreSQL и миграции проверяются в GitHub Actions на Python 3.11 и 3.13.

## 🎮 Команды

| Команда | Назначение |
|---|---|
| `/debate [тема]` | Начать обычный спор |
| `/role [роль]` | Философ, юрист, шутник или циник |
| `/difficulty [уровень]` | Новичок, опытный или эксперт |
| `/summary` | Резюме тезисов обеих сторон |
| `/judge` | Независимое анонимное судейство |
| `/fallacies` | Анализ логических ошибок пользователя |
| `/tournament` | Турнир из трёх раундов |
| `/history [1-10]` | Недавние сохранённые споры |
| `/rematch` | Повторить последнюю тему |
| `/export [current\|last\|N]` | Выгрузить спор в Markdown |
| `/stats` | Расширенная статистика и прогресс |
| `/achievements` | Открытые и закрытые достижения |
| `/leaderboard` | Таблица лидеров |
| `/privacy` | Политика хранения данных |
| `/delete_me` | Безвозвратно удалить свои данные |
| `/cancel` | Сохранить и завершить активный спор |

## 🗄 Архитектура хранения

**Redis** хранит только оперативные данные:

- активный спор и его историю;
- выбранную роль и сложность;
- блокировки запросов и rate limiting;
- временный выбор темы и подтверждение удаления.

**PostgreSQL** хранит постоянные данные:

- профиль пользователя и Telegram `user_id`;
- турнирную статистику, XP, уровни и достижения;
- счётчики логических ошибок;
- до 30 последних архивов споров;
- до 80 сообщений в одном архиве.

Повторная запись одного `session_id` обновляет архив и не увеличивает статистику второй раз.

## 🚀 Запуск через Docker Compose

```bash
git clone https://github.com/Onmaynec/DisputesBot.git
cd DisputesBot
cp .env.example .env
```

Заполните в `.env` как минимум:

```dotenv
BOT_TOKEN=telegram_bot_token
OPENAI_API_KEY=openai_api_key
DATABASE_URL=postgresql+asyncpg://disputesbot:disputesbot@postgres:5432/disputesbot
REDIS_URL=redis://redis:6379/0
```

Запуск:

```bash
docker compose up -d --build
```

Контейнер бота дождётся Redis и PostgreSQL, выполнит `alembic upgrade head`, затем запустит polling.

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

Установка и запуск:

```bash
pip install -e ".[dev]"
alembic upgrade head
python -m bot.main
```

Для локального PostgreSQL укажите адрес с асинхронным драйвером:

```dotenv
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/disputesbot
```

## ⬆️ Обновление с v0.3

Перед обновлением сохраните JSON и резервную копию каталога данных:

```bash
cp data/leaderboard.json data/leaderboard.backup.json
```

Поднимите PostgreSQL и примените миграции:

```bash
docker compose up -d postgres
docker compose run --rm disputes-bot alembic upgrade head
```

Проверьте старый JSON без записи:

```bash
docker compose run --rm disputes-bot \
  python -m bot.import_json --path data/leaderboard.json --dry-run
```

Импортируйте данные:

```bash
docker compose run --rm disputes-bot \
  python -m bot.import_json --path data/leaderboard.json
```

Импорт идемпотентен: повторный запуск обновляет существующие профили и архивы, не создавая дубликаты.

После проверки запустите весь стек:

```bash
docker compose up -d --build
```

## 💾 Резервное копирование

Создать дамп:

```bash
docker compose exec postgres pg_dump \
  -U disputesbot -d disputesbot -Fc -f /tmp/disputesbot.dump
docker compose cp postgres:/tmp/disputesbot.dump ./disputesbot.dump
```

Восстановить дамп в пустую базу:

```bash
docker compose cp ./disputesbot.dump postgres:/tmp/disputesbot.dump
docker compose exec postgres pg_restore \
  -U disputesbot -d disputesbot --clean --if-exists /tmp/disputesbot.dump
```

## 🔐 Приватность

`/delete_me` создаёт одноразовое подтверждение на пять минут. После подтверждения удаляются:

- профиль, статистика, достижения и архивы из PostgreSQL;
- активная сессия, роль, сложность и временные ключи из Redis;
- запись пользователя из таблицы лидеров.

Операция идемпотентна: повторное удаление не вызывает ошибку.

## 🧪 Проверки

```bash
ruff check .
python -m compileall -q bot tests migrations
pytest -q
alembic upgrade head
```

CI запускает Ruff, Alembic и полный pytest на Python 3.11 и 3.13 с отдельным PostgreSQL service container.

## 📁 Основные модули

```text
bot/database.py           SQLAlchemy models и async engine
bot/sql_profile_store.py  транзакционный PostgreSQL repository
bot/import_json.py        импорт JSON-профилей v0.2/v0.3
bot/privacy.py            одноразовые подтверждения удаления
bot/exporter.py           безопасный Markdown-экспорт
bot/v04_handlers.py       /privacy, /delete_me и /export
migrations/               Alembic migrations
```

## 📄 Лицензия

MIT — см. [LICENSE](LICENSE).
