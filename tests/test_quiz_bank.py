import json

import pytest
from pydantic import ValidationError

from app.core.training_profile import TrainingProfile
from app.services.quiz_bank import load_quiz_bank


def make_profile():
    return TrainingProfile.model_validate(
        {
            "profile_id": "demo-onboarding",
            "version": 1,
            "title": "Demo",
            "learning": {"material_file": "materials/demo.md"},
            "tutor": {
                "system_prompt_file": "prompts/tutor_system.txt"
            },
            "quiz": {
                "question_count": 2,
                "passing_score_percent": 80,
            },
        }
    )


def make_bank():
    return {
        "profile_id": "demo-onboarding",
        "profile_version": 1,
        "questions": [
            {
                "question_id": f"q{i}",
                "text": f"Question {i}",
                "options": ["A", "B", "C", "D"],
                "correct_option": 0,
            }
            for i in range(1, 3)
        ],
    }


def write_bank(tmp_path, data):
    path = tmp_path / "quiz.json"
    path.write_text(
        json.dumps(data, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def test_load_valid_bank(tmp_path):
    path = write_bank(tmp_path, make_bank())

    bank = load_quiz_bank(path, make_profile(), tmp_path)

    assert len(bank.questions) == 2


def test_profile_id_mismatch(tmp_path):
    data = make_bank()
    data["profile_id"] = "another-profile"
    path = write_bank(tmp_path, data)

    with pytest.raises(ValueError, match="profile_id mismatch"):
        load_quiz_bank(path, make_profile(), tmp_path)


def test_profile_version_mismatch(tmp_path):
    data = make_bank()
    data["profile_version"] = 2
    path = write_bank(tmp_path, data)

    with pytest.raises(ValueError, match="version mismatch"):
        load_quiz_bank(path, make_profile(), tmp_path)


def test_question_count_mismatch(tmp_path):
    data = make_bank()
    data["questions"].pop()
    path = write_bank(tmp_path, data)

    with pytest.raises(ValueError, match="question count mismatch"):
        load_quiz_bank(path, make_profile(), tmp_path)


def test_duplicate_question_ids(tmp_path):
    data = make_bank()
    data["questions"][1]["question_id"] = "q1"
    path = write_bank(tmp_path, data)

    with pytest.raises(ValidationError, match="unique"):
        load_quiz_bank(path, make_profile(), tmp_path)


def test_path_outside_project_rejected(tmp_path):
    with pytest.raises(ValueError, match="outside project root"):
        load_quiz_bank(
            "../outside.json",
            make_profile(),
            tmp_path,
        )


def test_missing_bank(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_quiz_bank(
            "missing.json",
            make_profile(),
            tmp_path,
        )
