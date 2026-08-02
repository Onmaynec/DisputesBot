<div align="center">

# ⚔️ DisputesBot v0.14

**Telegram-бот для тренировки дебатов, логики и критического мышления**

![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![aiogram](https://img.shields.io/badge/aiogram-3.30.0-2CA5E0)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-ranked%20rewards-336791)
![Redis](https://img.shields.io/badge/Redis-ranked%20matchmaking-red)
![Version](https://img.shields.io/badge/version-0.14.0-brightgreen)

</div>

## ✨ Новое в v0.14

- 🎁 `/ranked_rewards` показывает награды всех рейтинговых лиг;
- ✅ `/claim_ranked_rewards` атомарно начисляет доступные PvP-токены;
- 📈 доступность определяется по лучшему Elo текущего сезона;
- 🧭 награды остаются закрытыми до завершения пяти калибровочных матчей;
- 🔒 каждый дивизион можно получить только один раз за сезон;
- 🗄️ добавлена миграция `0008_ranked_rewards`;
- ♻️ private coaching v0.13, ranked matchmaking, daily-награды и магазин сохранены.

## 🎁 Награды рейтинговых лиг

После завершения калибровки игрок получает право забрать все milestones до максимального
достигнутого Elo сезона. Последующее падение рейтинга не отменяет заработанную награду.

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

`/ranked_rewards` показывает текущую лигу, лучший Elo сезона, баланс, полученные,
доступные и закрытые milestones. Claim накопительный: при первом достижении Платины
будут выданы ещё не полученные награды Бронзы, Серебра, Золота и Платины.

Начисление выполняется одной PostgreSQL-транзакцией. Сезонная PvP-запись и кошелёк
блокируются, а составной ключ `(user_id, season, league_id)` исключает повторную выдачу.
Токены не меняют Elo, season points, matchmaking, судейство или результат матча.

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
навыки, результаты, тренд, сильную сторону, фокус тренировки и сравнение позиций
«за»/«против». Отчёт использует сохранённые score payload и не вызывает OpenAI повторно.

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
кандидатов выбирается минимальная разница Elo, затем время ожидания и Telegram user ID.

## 🏆 Рейтинговые лиги

Первые пять завершённых PvP-матчей считаются калибровочными. Elo изменяется сразу,
но дивизион и ranked rewards открываются после placement.

```text
/league               дивизион, место, форма и прогресс
/league_top           топ-10 сезона с дивизионами
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

## ⚔️ PvP-команды

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
| `/pvp_leaderboard` | Топ-10 по Elo |
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

## 🗄️ Хранилища

### PostgreSQL

Профили, архивы, сезонный Elo, завершённые матчи и судейские оценки, blocklist,
жалобы, progression wallets, daily claims, косметика, публичность профиля,
персональные вызовы и журнал полученных наград рейтинговых лиг.

`pvp_ranked_reward_claims` хранит только Telegram user ID, сезон, ID дивизиона,
число токенов, Elo при claim и время операции. Аргументы, стенограммы и судейские
оценки в reward-table не копируются.

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

## ⬆️ Обновление с v0.13

```bash
git pull
pip install -e ".[dev]"
alembic upgrade head
```

Миграция `0008_ranked_rewards` создаёт одну таблицу claim-аудита и индекс по сезону и
дивизиону. Существующие профили, coaching, матчи, Elo, кошельки, косметика, вызовы и
очереди не изменяются.

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

`/delete_me` удаляет профиль, архивы, PvP-рейтинг, матчи и coaching-источник,
progression wallet, daily claims, ranked reward claims, косметику, публичность,
вызовы, blocklist, обе очереди и активные Redis-сессии. Жалобы остаются
обезличенными аудиторскими записями.

## 📄 Лицензия

MIT
