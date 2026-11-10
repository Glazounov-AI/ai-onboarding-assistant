import json

import pytest

from app.core.quiz import QuizBank, QuizQuestion
from app.services.quiz_drafts import QuizDraftError, save_quiz_draft


def make_bank(profile_id="demo-onboarding"):
    return QuizBank(
        profile_id=profile_id,
        profile_version=1,
        questions=[
            QuizQuestion(
                question_id="q1",
                text="Где фиксируются задачи?",
                options=["В трекере", "В чате", "Устно", "В блокноте"],
                correct_option=0,
                source_excerpt="Все рабочие задачи фиксируются в трекере.",
            )
        ],
    )


def test_save_draft(tmp_path):
    path = save_quiz_draft(make_bank(), tmp_path)

    assert path.is_file()
    assert path.parent == tmp_path / "quizzes" / "drafts"

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["profile_id"] == "demo-onboarding"


def test_existing_draft_not_overwritten(tmp_path):
    bank = make_bank()
    path = save_quiz_draft(bank, tmp_path)
    original_content = path.read_text(encoding="utf-8")

    with pytest.raises(QuizDraftError, match="already exists"):
        save_quiz_draft(bank, tmp_path)

    assert path.read_text(encoding="utf-8") == original_content


def test_invalid_profile_id_rejected(tmp_path):
    bank = make_bank(profile_id="../outside")

    with pytest.raises(QuizDraftError, match="outside drafts directory"):
        save_quiz_draft(bank, tmp_path)
