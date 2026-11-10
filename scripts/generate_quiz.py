
import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI

from app.core.training_profile import (
    load_training_material,
    load_training_profile,
)
from app.services.quiz_drafts import save_quiz_draft
from app.services.quiz_generator import QuizGenerator

ROOT = Path(__file__).resolve().parents[1]


async def main(project_root: Path = ROOT) -> None:
    load_dotenv(project_root / ".env")

    profile = load_training_profile(
        project_root / "config" / "training.example.yaml"
    )
    material = load_training_material(profile, project_root)

    draft_path = (
        project_root
        / "quizzes"
        / "drafts"
        / f"{profile.profile_id}-v{profile.version}.json"
    )

    if draft_path.exists():
        print(f"Черновик уже существует: {draft_path}")
        print("Генерация отменена. Запрос к OpenAI не отправлялся.")
        return

    prompt_path = project_root / "prompts" / "quiz_generator_system.txt"
    system_prompt = prompt_path.read_text(encoding="utf-8").strip()

    if not system_prompt:
        raise ValueError("Quiz generator system prompt is empty")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not configured")

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    base_url = os.getenv("OPENAI_BASE_URL") or None

    async with AsyncOpenAI(
        api_key=api_key,
        base_url=base_url,
    ) as client:
        generator = QuizGenerator(
            client=client,
            model=model,
            system_prompt=system_prompt,
        )

        bank = await generator.generate(profile, material)
        path = save_quiz_draft(bank, project_root)

    print(f"Generated questions: {len(bank.questions)}")
    print(f"Draft saved: {path}")


if __name__ == "__main__":
    asyncio.run(main())
