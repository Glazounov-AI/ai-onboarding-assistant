
import pytest

from app.core.quiz import QuizBank, QuizQuestion
from app.services.quiz_sources import (
    QuizSourceError,
    validate_quiz_sources,
)

MATERIAL = """
Все рабочие задачи фиксируются в трекере.

Важные решения документируются письменно.
"""


def make_bank(excerpt: str | None) -> QuizBank:
    return QuizBank(
        profile_id="demo-onboarding",
        profile_version=1,
        questions=[
            QuizQuestion(
                question_id="q1",
                text="Где фиксируются рабочие задачи?",
                options=[
                    "В трекере",
                    "В блокноте",
                    "В чате",
                    "Устно",
                ],
                correct_option=0,
                source_excerpt=excerpt,
            )
        ],
    )


def test_valid_source_excerpt():
    bank = make_bank(
        "Все рабочие задачи фиксируются в трекере."
    )

    validate_quiz_sources(bank, MATERIAL)


def test_source_excerpt_with_different_whitespace():
    bank = make_bank(
        "Все рабочие задачи   фиксируются\nв трекере."
    )

    validate_quiz_sources(bank, MATERIAL)


def test_missing_source_excerpt():
    bank = make_bank(None)

    with pytest.raises(
        QuizSourceError,
        match="Missing source excerpt",
    ):
        validate_quiz_sources(bank, MATERIAL)


def test_fabricated_source_excerpt():
    bank = make_bank(
        "Все рабочие задачи фиксируются в электронной почте."
    )

    with pytest.raises(
        QuizSourceError,
        match="Source excerpt not found",
    ):
        validate_quiz_sources(bank, MATERIAL)


def test_empty_training_material():
    bank = make_bank(
        "Все рабочие задачи фиксируются в трекере."
    )

    with pytest.raises(
        QuizSourceError,
        match="Training material is empty",
    ):
        validate_quiz_sources(bank, "   ")
