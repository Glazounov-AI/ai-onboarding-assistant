import json
from pathlib import Path

from app.core.quiz import QuizBank


class QuizDraftError(ValueError):
    """Ошибка сохранения черновика теста."""


def save_quiz_draft(
    bank: QuizBank,
    project_root: str | Path,
) -> Path:
    root = Path(project_root).resolve()
    drafts_dir = (root / "quizzes" / "drafts").resolve()

    if not drafts_dir.is_relative_to(root):
        raise QuizDraftError("Draft directory is outside project root")

    drafts_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{bank.profile_id}-v{bank.profile_version}.json"
    draft_path = (drafts_dir / filename).resolve()

    if not draft_path.is_relative_to(drafts_dir):
        raise QuizDraftError("Draft path is outside drafts directory")

    try:
        with draft_path.open("x", encoding="utf-8") as file:
            json.dump(
                bank.model_dump(mode="json"),
                file,
                ensure_ascii=False,
                indent=2,
            )
    except FileExistsError as exc:
        raise QuizDraftError(
            f"Draft already exists: {draft_path}"
        ) from exc

    return draft_path
