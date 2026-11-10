import re

from app.core.quiz import QuizBank


class QuizSourceError(ValueError):
    """Ошибка подтверждения вопроса учебным материалом."""


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def validate_quiz_sources(
    bank: QuizBank,
    material: str,
) -> None:
    normalized_material = normalize_text(material)

    if not normalized_material:
        raise QuizSourceError("Training material is empty")

    for question in bank.questions:
        excerpt = question.source_excerpt

        if excerpt is None or not excerpt.strip():
            raise QuizSourceError(
                f"Missing source excerpt: {question.question_id}"
            )

        if normalize_text(excerpt) not in normalized_material:
            raise QuizSourceError(
                f"Source excerpt not found: {question.question_id}"
            )
