import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from openai import APIConnectionError

from app.core.training_profile import TrainingProfile
from app.services.quiz_generator import (
    QuizGenerationError,
    QuizGenerator,
)

MATERIAL = "Все рабочие задачи фиксируются в трекере."


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
                "question_count": 1,
                "passing_score_percent": 80,
            },
        }
    )


def make_response(content):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content)
            )
        ]
    )


def make_bank():
    return {
        "profile_id": "demo-onboarding",
        "profile_version": 1,
        "questions": [
            {
                "question_id": "q1",
                "text": "Где фиксируются задачи?",
                "options": ["В трекере", "В чате", "Устно", "В блокноте"],
                "correct_option": 0,
                "source_excerpt": MATERIAL,
            }
        ],
    }


def make_generator(response):
    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=response)
    return QuizGenerator(
        client=client,
        model="test-model",
        system_prompt="Generate quiz JSON",
    )


@pytest.mark.asyncio
async def test_generate_valid_bank():
    generator = make_generator(
        make_response(json.dumps(make_bank(), ensure_ascii=False))
    )

    bank = await generator.generate(make_profile(), MATERIAL)

    assert len(bank.questions) == 1
    assert bank.questions[0].correct_option == 0


@pytest.mark.asyncio
async def test_generate_invalid_json():
    generator = make_generator(make_response("{invalid"))

    with pytest.raises(QuizGenerationError, match="invalid quiz bank"):
        await generator.generate(make_profile(), MATERIAL)


@pytest.mark.asyncio
async def test_generate_wrong_question_count():
    data = make_bank()
    data["questions"].append(
        {**data["questions"][0], "question_id": "q2"}
    )
    generator = make_generator(make_response(json.dumps(data)))

    with pytest.raises(QuizGenerationError, match="question count"):
        await generator.generate(make_profile(), MATERIAL)


@pytest.mark.asyncio
async def test_generate_fabricated_source():
    data = make_bank()
    data["questions"][0]["source_excerpt"] = (
        "Задачи фиксируются в электронной почте."
    )
    generator = make_generator(make_response(json.dumps(data)))

    with pytest.raises(QuizGenerationError, match="source excerpts"):
        await generator.generate(make_profile(), MATERIAL)


@pytest.mark.asyncio
async def test_generate_api_error():
    client = MagicMock()
    client.chat.completions.create = AsyncMock(
        side_effect=APIConnectionError(request=MagicMock())
    )
    generator = QuizGenerator(
        client=client,
        model="test-model",
        system_prompt="Generate quiz JSON",
    )

    with pytest.raises(QuizGenerationError, match="temporarily unavailable"):
        await generator.generate(make_profile(), MATERIAL)


@pytest.mark.asyncio
async def test_generate_empty_material():
    generator = make_generator(make_response("{}"))

    with pytest.raises(ValueError, match="material cannot be empty"):
        await generator.generate(make_profile(), "  ")


@pytest.mark.asyncio
async def test_generate_duplicate_source_excerpts():
    data = make_bank()

    duplicate = {
        **data["questions"][0],
        "question_id": "q2",
        "text": "Как фиксируются задачи команды?",
    }

    data["questions"].append(duplicate)

    generator = make_generator(
        make_response(json.dumps(data, ensure_ascii=False))
    )

    profile_data = make_profile().model_dump()
    profile_data["quiz"]["question_count"] = 2
    profile = TrainingProfile.model_validate(profile_data)

    with pytest.raises(
        QuizGenerationError,
        match="duplicate source excerpts",
    ):
        await generator.generate(profile, MATERIAL)
