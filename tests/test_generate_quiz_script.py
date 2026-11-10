
from unittest.mock import patch

import pytest

from scripts.generate_quiz import main


@pytest.mark.asyncio
async def test_existing_draft_skips_openai(tmp_path):
    profile_dir = tmp_path / "config"
    profile_dir.mkdir()

    profile_file = profile_dir / "training.example.yaml"
    profile_file.write_text(
        """
profile_id: demo-onboarding
version: 1
title: Demo
learning:
  material_file: materials/demo.md
quiz:
  question_count: 1
  passing_score_percent: 80
tutor:
  system_prompt_file: prompts/tutor_system.txt
""",
        encoding="utf-8",
    )

    material_dir = tmp_path / "materials"
    material_dir.mkdir()
    (material_dir / "demo.md").write_text(
        "Учебный материал",
        encoding="utf-8",
    )

    draft_dir = tmp_path / "quizzes" / "drafts"
    draft_dir.mkdir(parents=True)
    (draft_dir / "demo-onboarding-v1.json").write_text(
        "{}",
        encoding="utf-8",
    )

    with patch(
        "scripts.generate_quiz.AsyncOpenAI"
    ) as mock_openai:
        await main(project_root=tmp_path)

    mock_openai.assert_not_called()
