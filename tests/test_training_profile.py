
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.training_profile import (
    TrainingProfile,
    load_training_material,
    load_training_profile,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_load_example_profile():
    profile = load_training_profile(
        PROJECT_ROOT / "config/training.example.yaml"
    )

    assert profile.profile_id == "demo-onboarding"
    assert profile.quiz.question_count == 5
    assert profile.quiz.passing_score_percent == 80


def test_load_example_material():
    profile = load_training_profile(
        PROJECT_ROOT / "config/training.example.yaml"
    )

    material = load_training_material(profile, PROJECT_ROOT)

    assert "трекере" in material
    assert len(material) > 20


def test_invalid_quiz_question_count():
    with pytest.raises(ValidationError):
        TrainingProfile.model_validate(
            {
                "profile_id": "test",
                "version": 1,
                "title": "Test",
                "learning": {"material_file": "materials/demo.md"},
                "quiz": {
                    "question_count": 0,
                    "passing_score_percent": 80,
                },
            }
        )


def test_material_path_traversal_is_rejected(tmp_path):
    profile = TrainingProfile.model_validate(
        {
            "profile_id": "test",
            "version": 1,
            "title": "Test",
            "learning": {
                "material_file": "../outside.md",
            },
            "quiz": {
                "question_count": 5,
                "passing_score_percent": 80,
            },
        }
    )

    with pytest.raises(ValueError, match="outside project root"):
        load_training_material(profile, tmp_path)


def test_missing_material(tmp_path):
    profile = TrainingProfile.model_validate(
        {
            "profile_id": "test",
            "version": 1,
            "title": "Test",
            "learning": {
                "material_file": "materials/missing.md",
            },
            "quiz": {
                "question_count": 5,
                "passing_score_percent": 80,
            },
        }
    )

    with pytest.raises(FileNotFoundError):
        load_training_material(profile, tmp_path)
