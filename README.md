<div align="center">

# ⚔️ DisputesBot v0.5

**Telegram-бот для тренировки дебатов, логики и критического мышления**

![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![aiogram](https://img.shields.io/badge/aiogram-3.30.0-2CA5E0)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-profiles%20%26%20Elo-336791)
![Redis](https://img.shields.io/badge/Redis-sessions%20%26%20PvP-red)
![Version](https://img.shields.io/badge/version-0.5.0-brightgreen)

</div>

## ✨ Новое в v0.5

- ⚔️ рейтинговые PvP-дуэли между двумя реальными пользователями;
- 📨 `/duel [тема]` создаёт приглашение с inline-кнопкой;
- 🔎 `/queue [тема]` подбирает свободного соперника;
- 🔄 активный матч восстанавливается из Redis после перезапуска;
- 🎯 позиции «за» и «против» распределяются случайно и больше не меняются;
- 🧠 независимый судья получает только анонимных участников A/B;
- 🏅 отдельный сезонный Elo-рейтинг с коэффициентом K=32;
- 📊 `/rating`, `/pvp_leaderboard` и `/duel_history`;
- 🏳 `/forfeit` завершает начатую дуэль поражением;
- 🛑 `/cancel_duel` отменяет матч до первого аргумента без изменения Elo.

Одиночные споры, турниры, достижения, приватность и Markdown-экспорт из v0.4 сохранены.

## 🎮 Команды

### PvP

| Команда | Назначение |
|---|---|
| `/duel [тема]` | Создать прямое приглашение в дуэль |
| `/queue [тема]` | Встать в очередь автоматического подбора |
| `/leave_queue` | Выйти из очереди |
| `/duel_status` | Показать позиции, прогресс и текущий ход |
| `/cancel_duel` | Отменить дуэль до первого аргумента |
| `/forfeit` | Сдаться после начала матча |
| `/rating` | Личный Elo и место в текущем сезоне |
| `/pvp_leaderboard` | Топ-10 игроков сезона |
| `/duel_history` | Последние пять PvP-матчей |

### Одиночные режимы

| Команда | Назначение |
|---|---|
| `/debate [тема]` | Начать обычный спор с ботом |
| `/role [роль]` | Философ, юрист, шутник или циник |
| `/difficulty [уровень]` | Новичок, опытный или эксперт |
| `/summary` | Резюме тезисов обеих сторон |
| `/judge` | Независимое анонимное судейство |
| `/fallacies` | Анализ логических ошибок |
| `/tournament` | Турнир из трёх раундов |
| `/history [1-10]` | Сохранённые одиночные споры |
| `/rematch` | Повторить последнюю тему |
| `/export [current\|last\|N]` | Выгрузить спор в Markdown |
| `/stats` | Статистика и прогресс |
| `/achievements` | Достижения |
| `/leaderboard` | Лидерборд одиночных турниров |
| `/privacy` | Политика хранения данных |
| `/delete_me` | Удалить свои PostgreSQL- и Redis-данные |
| `/cancel` | Завершить одиночный спор |

## ⚔️ Как проходит PvP-дуэль

1. Первый пользователь создаёт `/duel [тема]` или входит в `/queue [тема]`.
2. После появления второго участника бот случайно назначает стороны «за» и «против».
3. Сторона «за» делает первый ход.
4. Ходы строго чередуются; у каждого участника три аргумента.
5. После шестого аргумента матч блокируется для новых ходов и передаётся независимому судье.
6. Судья оценивает логику, доказательность и работу с возражениями.
7. PostgreSQL транзакционно обновляет Elo обоих игроков и сохраняет один результат по `match_id`.

Повторная запись того же `match_id` возвращает существующий результат и не меняет рейтинг второй раз.

## 🏅 Elo и сезоны

- начальный рейтинг: **1000 Elo**;
- коэффициент: **K=32**;
- победа, поражение и ничья обновляют рейтинги симметрично;
- сумма изменений Elo двух игроков всегда равна нулю;
- PvP-рейтинг отделён от старого турнирного лидерборда;
- текущий сезон задаётся переменной `PVP_SEASON`.

Для нового сезона достаточно изменить `PVP_SEASON`: старые результаты остаются в PostgreSQL, а игроки получают отдельную сезонную запись с начальным Elo 1000.

## 🗄 Архитектура хранения

**Redis** хранит оперативное состояние:

- одиночные активные споры;
- живые PvP-матчи и индекс участник → матч;
- приглашения и очередь подбора;
- выбранную роль и сложность;
- блокировки, rate limiting и подтверждения удаления.

**PostgreSQL** хранит постоянные данные:

- профили и Telegram `user_id`;
- одиночную статистику, XP и достижения;
- архивы одиночных споров;
- сезонные PvP-рейтинги;
- завершённые PvP-матчи, изменения Elo, вердикт и стенограмму.

Команда `/delete_me` удаляет профиль, архивы, PvP-рейтинг, историю матчей и временные Redis-ключи.

## 🚀 Запуск через Docker Compose

```bash
git clone https://github.com/Onmaynec/DisputesBot.git
cd DisputesBot
cp .env.example .env
```

Заполните минимум:

```dotenv
BOT_TOKEN=telegram_bot_token
OPENAI_API_KEY=openai_api_key
DATABASE_URL=postgresql+asyncpg://disputesbot:disputesbot@postgres:5432/disputesbot
REDIS_URL=redis://redis:6379/0
PVP_SEASON=season-1
```

Запуск:

```bash
docker compose up -d --build
```

Контейнер бота дождётся Redis и PostgreSQL, применит `alembic upgrade head`, затем запустит polling.

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

## ⬆️ Обновление с v0.4

1. Создайте резервную копию PostgreSQL.
2. Обновите код и `.env.example`.
3. Добавьте `PVP_SEASON=season-1` или собственный идентификатор сезона.
4. Примените миграцию:

```bash
docker compose run --rm disputes-bot alembic upgrade head
```

5. Перезапустите стек:

```bash
docker compose up -d --build
```

Миграция `0002_pvp` добавляет новые таблицы и не изменяет существующие профили или архивы v0.4.

## 🧹 Очистка зависшего PvP-состояния

Активные матчи имеют TTL `PVP_MATCH_TTL_SECONDS`. Для штатного завершения используйте `/duel_status`, `/forfeit` или `/cancel_duel`.

При аварийном ручном обслуживании Redis удалите ключ матча и оба пользовательских индекса с префиксом:

```text
<REDIS_PREFIX>:pvp:match:<match_id>
<REDIS_PREFIX>:pvp:user:<telegram_user_id>
```

Постоянный завершённый результат в PostgreSQL при этом не затрагивается.

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

CI запускает Ruff, Alembic и полный pytest на Python 3.11 и 3.13 с PostgreSQL 17.

## 📁 Основные модули

```text
bot/pvp_models.py       строгая модель PvP-матча и переходы состояний
bot/pvp_store.py        Redis-матчи, приглашения, очередь и блокировки
bot/pvp_repository.py   сезонный Elo и история матчей в PostgreSQL
bot/pvp_judge_utils.py  анонимизация A/B
bot/v05_handlers.py     PvP-команды и обработка ходов
bot/database.py         SQLAlchemy-модели
migrations/             Alembic-миграции
```

## 📄 Лицензия

MIT — см. [LICENSE](LICENSE).
