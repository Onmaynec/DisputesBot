import pytest
from pydantic import ValidationError

from bot.schemas import FallacyAnalysisOutput


def test_fallacy_output_accepts_empty_result() -> None:
    result = FallacyAnalysisOutput(
        fallacies=[],
        overall_advice="Добавьте проверяемую причинную связь и конкретный пример.",
    )
    assert result.fallacies == []


def test_fallacy_output_rejects_invalid_confidence() -> None:
    with pytest.raises(ValidationError):
        FallacyAnalysisOutput.model_validate(
            {
                "fallacies": [
                    {
                        "name": "Ложная дилемма",
                        "excerpt": "Есть только два варианта",
                        "explanation": "Другие варианты не были рассмотрены.",
                        "improvement": "Перечислите дополнительные реалистичные варианты.",
                        "confidence": "абсолютная",
                    }
                ],
                "overall_advice": "Проверяйте полноту набора альтернатив.",
            }
        )
