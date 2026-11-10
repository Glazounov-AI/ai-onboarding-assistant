
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field


class LearningConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_file: str
    allow_questions: bool = True


class QuizConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bank_file: str = Field(default="quizzes/demo.json", min_length=1)
    question_count: int = Field(ge=1, le=50)
    passing_score_percent: int = Field(ge=0, le=100)
    allow_retry: bool = True


class TutorConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    system_prompt_file: str = Field(min_length=1)
    temperature: float = Field(default=0.2, ge=0, le=2)


class TrainingProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tutor: TutorConfig
    profile_id: str = Field(min_length=1)
    version: int = Field(ge=1)
    title: str = Field(min_length=1)
    language: str = "ru"
    learning: LearningConfig
    quiz: QuizConfig
   

def load_training_profile(path: str | Path) -> TrainingProfile:
    profile_path = Path(path).resolve()

    with profile_path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    if not isinstance(data, dict):
        raise TypeError("Training profile must be a YAML mapping")

    return TrainingProfile.model_validate(data)


def load_training_material(
    profile: TrainingProfile,
    project_root: str | Path,
) -> str:
    root = Path(project_root).resolve()
    material_path = (root / profile.learning.material_file).resolve()

    if not material_path.is_relative_to(root):
        raise ValueError("Training material path is outside project root")

    if not material_path.is_file():
        raise FileNotFoundError(
            f"Training material not found: {material_path}"
        )

    content = material_path.read_text(encoding="utf-8").strip()

    if not content:
        raise ValueError("Training material is empty")

    return content


def load_system_prompt(
    profile: TrainingProfile,
    project_root: str | Path,
) -> str:
    root = Path(project_root).resolve()
    prompt_path = (root / profile.tutor.system_prompt_file).resolve()

    if not prompt_path.is_relative_to(root):
        raise ValueError("System prompt path is outside project root")

    if not prompt_path.is_file():
        raise FileNotFoundError(
            f"System prompt not found: {prompt_path}"
        )

    content = prompt_path.read_text(encoding="utf-8").strip()

    if not content:
        raise ValueError("System prompt is empty")

    return content