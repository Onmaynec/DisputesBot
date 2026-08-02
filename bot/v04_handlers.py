from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from .challenge_repository import ChallengeRepository
from .cosmetic_repository import CosmeticRepository
from .exporter import export_filename, render_archive_markdown, render_session_markdown
from .moderation_repository import ModerationRepository
from .privacy import PrivacyConfirmationStore
from .profile_protocol import ProfileRepository
from .progression_repository import ProgressionRepository
from .pvp_repository import PvPRepository
from .pvp_store import PvPStore
from .ranked_reward_repository import RankedRewardRepository
from .season_goal_repository import SeasonGoalRepository
from .social_repository import SocialRepository
from .storage import SessionStore

router = Router(name="v04")


def delete_confirmation_keyboard(token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🗑 Удалить мои данные",
                    callback_data=f"privacy:delete:{token}",
                )
            ],
            [InlineKeyboardButton(text="Отмена", callback_data="privacy:cancel")],
        ]
    )


@router.message(CommandStart())
async def start_v04_command(message: Message) -> None:
    await message.answer(
        "⚔️ Добро пожаловать в DisputesBot v0.17!\n\n"
        "Тренируйте аргументацию с ботом или участвуйте в PvP-дуэлях.\n\n"
        "Новые команды:\n"
        "/goals — сезонные PvP-цели и прогресс\n"
        "/set_goal — создать или изменить измеримую цель\n"
        "/goal_suggest — получить персональные рекомендации\n\n"
        "Итоги: /season_recap · /compare_seasons · /career_records\n"
        "Карьера и архив: /pvp_career · /season_archive · /hall_of_fame\n"
        "Награды лиг: /ranked_rewards · /claim_ranked_rewards\n"
        "Coaching: /match_review · /pvp_coach\n"
        "Рейтинговый подбор: /ranked_queue · /queue_status\n"
        "Лига: /league\n"
        "Персональные вызовы: /challenge · /challenges\n"
        "Магазин косметики: /shop\n"
        "Ежедневные задания: /daily\n"
        "Начать спор: /debate [тема]"
    )


PRIVACY_TEXT = """🔐 Приватность DisputesBot

Постоянно сохраняются:
• Telegram user_id, username и отображаемое имя;
• турнирная статистика, XP и достижения;
• до 30 последних архивов споров;
• сезонный PvP Elo и история завершённых дуэлей;
• структурированные судейские оценки logic, evidence и rebuttal для полных PvP-матчей;
• пользовательский PvP-блок-лист;
• жалобы на матчи и журнал их обработки;
• сезонные очки, PvP-токены, серии дней и полученные daily-награды;
• полученные награды рейтинговых лиг, сумма токенов и Elo в момент claim;
• приватные сезонные цели: ID метрики, стартовое и целевое значение, время завершения;
• купленные косметические item ID и выбранный сезонный loadout;
• настройка публичности PvP-профиля;
• персональные PvP-вызовы, их тема, статус и срок действия.

Публичность профиля по умолчанию выключена. После /profile_visibility public другие
пользователи могут видеть PvP Elo, сезонную статистику, очки и экипированную косметику.
Баланс токенов, история наград и сезонные цели другим пользователям не показываются.
Блокировка в любую сторону запрещает просмотр профиля и создание или принятие
персонального вызова. /rivals и /head_to_head показывают только статистику матчей,
в которых участвовал сам запрашивающий пользователь.

/goals, /set_goal, /delete_goal и /goal_suggest доступны только владельцу Telegram
user ID. Цели содержат фиксированный ID метрики и числовые значения, но не сохраняют
свободный текст. Прогресс вычисляется из существующих Elo, матчей и судейских оценок.
Выполнение фиксируется один раз, не начисляет токены и не влияет на Elo, matchmaking,
судейство или исход матча. Рекомендации детерминированы и не вызывают OpenAI.

/match_review и /pvp_coach доступны только владельцу Telegram user ID и анализируют
только матчи, в которых он участвовал. Coaching-layer не создаёт новые оценки, не
вызывает OpenAI повторно и не сохраняет отдельный профиль навыков: отчёт вычисляется
при запросе из уже сохранённых результатов. Матчи через сдачу или тайм-аут без
структурированных оценок в coaching-статистику не входят.

/season_recap, /compare_seasons и /career_records доступны только владельцу аккаунта.
Они вычисляют Elo-путь, ранг, серии, соперников, средние судейские навыки и полученные
ranked rewards из уже сохранённых строк. Отдельные recap, comparison или record-профили
не создаются и новые запросы к OpenAI не выполняются.

/pvp_career вычисляет личную карьеру только из сезонных строк и матчей владельца.
/season_archive и /hall_of_fame показывают те же публичные агрегаты Elo, отображаемые
имена и число матчей, которые используются текущими лидербордами. Они не создают
отдельную копию профиля и не раскрывают стенограммы, аргументы или оценки судьи.

Рейтинговая лига и лучший Elo сезона вычисляются из агрегатов Elo и завершённых матчей.
Для защиты от повторного начисления PostgreSQL хранит только ID пользователя, сезон,
ID полученного дивизиона, число токенов, Elo в момент claim и время операции. Награды
не содержат аргументы, стенограммы или оценки судьи.

Персональные вызовы хранятся в PostgreSQL до принятия, отклонения, отмены или истечения
срока. Они содержат только ID участников, сезон, тему и служебный статус. Тексты будущих
аргументов в вызове не сохраняются.

В Redis временно хранятся активный спор, PvP-матч, приглашения, роль, сложность,
блокировки запросов, rate limit и записи обычной или рейтинговой очереди. Для
рейтингового подбора запись очереди дополнительно содержит временный снимок Elo,
число завершённых матчей, режим, тему и время входа. Она удаляется после подбора,
выхода, удаления аккаунта или истечения queue TTL.

Участник PvP видит имя и аргументы своего соперника. Команда /delete_me удаляет профиль,
архивы, PvP-рейтинг, историю матчей вместе с оценками, progression-данные, ranked reward
claims, сезонные цели, косметический инвентарь, настройку публичности, персональные
вызовы, обе очереди, blocklist, настройки и активные Redis-сессии. После удаления
исходных строк пользователь исчезает из карьеры, recap, сравнений, личных рекордов,
сезонных архивов и Hall of Fame. Жалобы сохраняются как аудиторские записи, но связь
с удалённым заявителем очищается."""


@router.message(Command("privacy"))
async def privacy_command(message: Message) -> None:
    await message.answer(PRIVACY_TEXT)


@router.message(Command("delete_me"))
async def delete_me_command(
    message: Message,
    privacy: PrivacyConfirmationStore,
) -> None:
    if message.from_user is None:
        return
    token = await privacy.create(message.from_user.id)
    await message.answer(
        "⚠️ Это безвозвратно удалит статистику, достижения, архивы, настройки, "
        "сезонный прогресс, цели, рейтинговые награды, косметический инвентарь, "
        "публичность, персональные вызовы, PvP-очереди и активный спор. "
        "Подтверждение действует 5 минут.",
        reply_markup=delete_confirmation_keyboard(token),
    )


@router.callback_query(F.data == "privacy:cancel")
async def cancel_delete_callback(
    callback: CallbackQuery,
    privacy: PrivacyConfirmationStore,
) -> None:
    await privacy.cancel(callback.from_user.id)
    await callback.answer("Удаление отменено")
    if callback.message is not None:
        await callback.message.edit_text("✅ Удаление данных отменено.")


@router.callback_query(F.data.startswith("privacy:delete:"))
async def confirm_delete_callback(
    callback: CallbackQuery,
    privacy: PrivacyConfirmationStore,
    leaderboard: ProfileRepository,
    pvp_store: PvPStore,
    pvp_repository: PvPRepository,
    moderation_repository: ModerationRepository,
    progression_repository: ProgressionRepository,
    cosmetic_repository: CosmeticRepository,
    social_repository: SocialRepository,
    challenge_repository: ChallengeRepository,
    ranked_reward_repository: RankedRewardRepository,
    season_goal_repository: SeasonGoalRepository,
) -> None:
    token = (callback.data or "").split(":", maxsplit=2)[-1]
    if not await privacy.consume(callback.from_user.id, token):
        await callback.answer("Подтверждение устарело", show_alert=True)
        if callback.message is not None:
            await callback.message.edit_text(
                "⌛ Подтверждение устарело. Запустите /delete_me ещё раз."
            )
        return
    await moderation_repository.anonymize_user(callback.from_user.id)
    await season_goal_repository.delete_user_data(callback.from_user.id)
    await ranked_reward_repository.delete_user_data(callback.from_user.id)
    await challenge_repository.delete_user_data(callback.from_user.id)
    await social_repository.delete_user_data(callback.from_user.id)
    await cosmetic_repository.delete_user_data(callback.from_user.id)
    await progression_repository.delete_user_data(callback.from_user.id)
    await pvp_repository.delete_user_data(callback.from_user.id)
    await leaderboard.delete_user(callback.from_user.id)
    await pvp_store.delete_user_data(callback.from_user.id)
    await privacy.delete_user_data(callback.from_user.id)
    await callback.answer("Данные удалены")
    if callback.message is not None:
        await callback.message.edit_text(
            "🗑 Ваш профиль, архивы, статистика, сезонный прогресс, цели, "
            "рейтинговые награды, косметика, публичность, вызовы, очереди, "
            "настройки и активная сессия удалены."
        )


@router.message(Command("export"))
async def export_command(
    message: Message,
    command: CommandObject,
    leaderboard: ProfileRepository,
    store: SessionStore,
) -> None:
    if message.from_user is None:
        return
    argument = (command.args or "current").strip().casefold()
    markdown: str | None = None
    topic = "debate"
    prefix = "debate"

    if argument in {"current", "текущий", ""}:
        session = await store.get_session(message.from_user.id)
        if session is not None:
            markdown = render_session_markdown(session)
            topic = session.topic
            prefix = "active"
        else:
            argument = "last"

    if argument in {"last", "последний"} and markdown is None:
        entry = await leaderboard.last_debate(message.from_user.id)
        if entry is not None:
            markdown = render_archive_markdown(entry)
            topic = entry.topic
            prefix = "archive"

    if argument.isdigit() and markdown is None:
        index = max(1, min(int(argument), 10))
        entries = await leaderboard.history(message.from_user.id, limit=index)
        if len(entries) >= index:
            entry = entries[index - 1]
            markdown = render_archive_markdown(entry)
            topic = entry.topic
            prefix = f"archive_{index}"

    if markdown is None:
        await message.answer(
            "Не найден спор для экспорта. Используйте /export current, /export last "
            "или /export 1."
        )
        return

    payload = BufferedInputFile(
        markdown.encode("utf-8"),
        filename=export_filename(topic, prefix=prefix),
    )
    await message.answer_document(payload, caption="📄 Экспорт спора в Markdown")
