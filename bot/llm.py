from __future__ import annotations

import json
import logging
import re
from collections import Counter
from typing import Any

from openai import AsyncOpenAI

from .models import DebateMessage, DebateSession, TournamentScores

logger = logging.getLogger(__name__)

ROLE_STYLES = {
    "философ": (
        "Рассуждай через определения, причинность, ценности и мысленные эксперименты. "
        "Не уходи в туманную абстракцию: связывай идеи с реальными последствиями."
    ),
    "юрист": (
        "Строй позицию как юрист: тезис, правило или принцип, факты, применение, вывод. "
        "Отмечай бремя доказательства и слабые допущения, но не выдумывай законы."
    ),
    "шутник": (
        "Добавляй лёгкий уместный юмор и яркие сравнения, сохраняя строгую логику. "
        "Не унижай собеседника и не превращай ответ в стендап."
    ),
    "циник": (
        "Проверяй идеалы на столкновение с интересами, стимулами и человеческими слабостями. "
        "Будь колким к идеям, но уважительным к человеку."
    ),
}

ROUND_FOCUS = {
    1: "Определения, базовые принципы и причинно-следственные связи",
    2: "Факты, примеры, контрпримеры и проверка допущений",
    3: "Практические последствия, компромиссы и итоговый синтез",
}


class DebateGenerationError(RuntimeError):
    pass


class DebateEngine:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str | None = None,
    ) -> None:
        client_kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        self.client = AsyncOpenAI(**client_kwargs)
        self.model = model

    async def close(self) -> None:
        await self.client.close()

    async def argument(
        self,
        session: DebateSession,
        *,
        opening: bool = False,
    ) -> str:
        if session.user_stance is None or session.bot_stance is None:
            raise ValueError("Stances must be set before generating an argument")

        focus = (
            ROUND_FOCUS[session.tournament_round]
            if session.mode.value == "tournament"
            else "точный ответ на последний тезис пользователя"
        )
        task = (
            "Дай первый аргумент своей стороны."
            if opening
            else "Ответь одним новым контраргументом на последний тезис пользователя."
        )
        instructions = self._base_instructions(session)
        prompt = f"""
Тема: {session.topic}
Позиция пользователя: {session.user_stance.value}
Твоя позиция: {session.bot_stance.value}
Текущий фокус: {focus}
Задача: {task}

Требования к ответу:
- ровно один основной аргумент;
- 3–6 предложений;
- тезис, объяснение и конкретный пример;
- уважительный, но настойчивый тон;
- не повторяй уже сказанное;
- не добавляй оценку спора, список советов или вопрос в конце.

История:
{self._history_text(session.history)}
""".strip()
        return await self._call(instructions, prompt, max_output_tokens=420)

    async def progress_review(self, session: DebateSession) -> str:
        prompt = f"""
Тема: {session.topic}
Позиция пользователя: {session.user_stance.value if session.user_stance else 'не указана'}

Проанализируй только аргументацию пользователя по истории ниже. Верни краткий разбор строго в формате:
Ваши сильные стороны: ...
Слабые места: ...
Следующий лучший ход: ...

Будь конкретным, приведи ссылку на один из тезисов пользователя своими словами. Не оценивай личность.

История:
{self._history_text(session.history)}
""".strip()
        return await self._call(self._base_instructions(session), prompt, max_output_tokens=380)

    async def summary(self, session: DebateSession) -> str:
        prompt = f"""
Сделай краткое нейтральное резюме спора на тему «{session.topic}».
Структура:
Тезисы пользователя:
- ...
Тезисы бота:
- ...
Точки согласия:
- ...
Главное расхождение:
- ...

Не добавляй новые аргументы. Объедини повторы. Максимум 180 слов.

История:
{self._history_text(session.history)}
""".strip()
        return await self._call(
            "Ты нейтральный редактор дебатов. Точно разделяй позиции сторон.",
            prompt,
            max_output_tokens=520,
        )

    async def judge(self, session: DebateSession) -> str:
        prompt = f"""
Выбери победителя спора на тему «{session.topic}» по качеству аргументации, а не по тому, чья позиция тебе ближе.
Критерии: ясность тезисов, логика, доказательность, работа с возражениями, отсутствие повторов.

Формат:
Победитель: Пользователь / Бот / Ничья
Обоснование: 3–5 предложений
Решающая деталь: 1 предложение

История:
{self._history_text(session.history)}
""".strip()
        return await self._call(
            "Ты беспристрастный судья дебатов. Не меняй критерии после анализа.",
            prompt,
            max_output_tokens=420,
        )

    async def round_feedback(self, session: DebateSession) -> str:
        round_number = session.tournament_round
        round_messages = [
            item for item in session.history if item.round_number == round_number
        ]
        prompt = f"""
Оцени раунд {round_number} турнирного спора на тему «{session.topic}».
Фокус раунда: {ROUND_FOCUS[round_number]}.

Формат:
Сильный ход: ...
Что ослабило позицию: ...
Как улучшить следующий раунд: ...

Оценивай пользователя, не личность. Максимум 110 слов.

Сообщения раунда:
{self._history_text(round_messages)}
""".strip()
        return await self._call(
            "Ты тренер по дебатам: конкретный, честный и доброжелательный.",
            prompt,
            max_output_tokens=360,
        )

    async def tournament_scores(self, session: DebateSession) -> TournamentScores:
        prompt = f"""
Оцени выступление пользователя в завершённом турнире на тему «{session.topic}».
Поставь целые баллы от 0 до 10 по критериям:
- logic: непротиворечивость и причинные связи;
- argumentation: доказательства, примеры, ответы на возражения;
- creativity: оригинальность формулировок и неожиданные, но уместные ходы.

Определи winner: "user", "bot" или "draw".
Верни только JSON без Markdown:
{{"logic": 0, "argumentation": 0, "creativity": 0, "winner": "draw", "reason": "краткое обоснование на русском"}}

История:
{self._history_text(session.history, limit=40)}
""".strip()
        raw = await self._call(
            "Ты строгий, но справедливый судья турнира дебатов.",
            prompt,
            max_output_tokens=320,
        )
        try:
            data = self._extract_json(raw)
            return TournamentScores(
                logic=self._score(data.get("logic")),
                argumentation=self._score(data.get("argumentation")),
                creativity=self._score(data.get("creativity")),
                winner=self._winner(data.get("winner")),
                reason=str(data.get("reason") or "Оценка основана на качестве тезисов и ответов."),
            )
        except (ValueError, TypeError, json.JSONDecodeError):
            logger.warning("Could not parse tournament score JSON: %s", raw)
            return self._fallback_scores(session)

    async def _call(
        self,
        instructions: str,
        prompt: str,
        *,
        max_output_tokens: int,
    ) -> str:
        try:
            response = await self.client.responses.create(
                model=self.model,
                instructions=instructions,
                input=prompt,
                max_output_tokens=max_output_tokens,
            )
        except Exception as exc:
            logger.exception("LLM request failed")
            raise DebateGenerationError("Не удалось получить ответ модели") from exc

        text = response.output_text.strip()
        if not text:
            raise DebateGenerationError("Модель вернула пустой ответ")
        return text

    @staticmethod
    def _base_instructions(session: DebateSession) -> str:
        style = ROLE_STYLES.get(session.role, ROLE_STYLES["философ"])
        return (
            "Ты — оппонент в учебном споре. Всегда защищай позицию, противоположную позиции "
            "пользователя. Будь уважительным, но настойчивым. Не соглашайся ради вежливости, "
            "не оскорбляй, не манипулируй и не выдумывай факты. Если тема зависит от свежих "
            "данных, прямо отмечай неопределённость. "
            f"Текущая роль: {session.role}. Стиль роли: {style}"
        )

    @staticmethod
    def _history_text(history: list[DebateMessage], limit: int = 24) -> str:
        if not history:
            return "История пока пуста."
        lines = []
        for item in history[-limit:]:
            author = "Пользователь" if item.author == "user" else "Бот"
            round_label = f" [раунд {item.round_number}]" if item.round_number else ""
            lines.append(f"{author}{round_label}: {item.text}")
        return "\n".join(lines)

    @staticmethod
    def _extract_json(raw: str) -> dict[str, Any]:
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("JSON object not found")
        payload = json.loads(raw[start : end + 1])
        if not isinstance(payload, dict):
            raise ValueError("Expected object")
        return payload

    @staticmethod
    def _score(value: Any) -> int:
        return max(0, min(10, int(round(float(value)))))

    @staticmethod
    def _winner(value: Any) -> str:
        normalized = str(value).casefold()
        return normalized if normalized in {"user", "bot", "draw"} else "draw"

    @staticmethod
    def _fallback_scores(session: DebateSession) -> TournamentScores:
        user_texts = [item.text for item in session.history if item.author == "user"]
        words = re.findall(r"[а-яa-z0-9-]+", " ".join(user_texts).casefold())
        unique_ratio = len(set(words)) / max(1, len(words))
        word_counts = Counter(words)
        connectors = (
            word_counts["потому"]
            + word_counts["например"]
            + word_counts["следовательно"]
        )
        length_score = min(10, 4 + len(words) // 45)
        logic = min(10, length_score + min(2, connectors))
        argumentation = min(10, 4 + min(6, len(user_texts) // 2))
        creativity = min(10, max(4, round(unique_ratio * 12)))
        total = logic + argumentation + creativity
        winner = "user" if total >= 22 else "draw" if total >= 17 else "bot"
        return TournamentScores(
            logic=logic,
            argumentation=argumentation,
            creativity=creativity,
            winner=winner,
            reason="Резервная оценка рассчитана по полноте, разнообразию и структуре аргументов.",
        )
