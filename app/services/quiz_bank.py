import json
from pathlib import Path

from app.core.quiz import QuizBank
from app.core.training_profile import TrainingProfile


def load_quiz_bank(
    path: str | Path,
    profile: TrainingProfile,
    project_root: str | Path,
) -> QuizBank:
    root = Path(project_root).resolve()
    bank_path = (root / path).resolve()

    if not bank_path.is_relative_to(root):
        raise ValueError("Quiz bank path is outside project root")

    if not bank_path.is_file():
        raise FileNotFoundError(
            f"Quiz bank not found: {bank_path}"
        )

    with bank_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    bank = QuizBank.model_validate(data)

    if bank.profile_id != profile.profile_id:
        raise ValueError("Quiz bank profile_id mismatch")

    if bank.profile_version != profile.version:
        raise ValueError("Quiz bank profile version mismatch")

    if len(bank.questions) != profile.quiz.question_count:
        raise ValueError("Quiz bank question count mismatch")

    return bank
