import json

from openai import AsyncOpenAI, OpenAIError
from pydantic import ValidationError

from app.core.quiz import QuizBank
from app.core.training_profile import TrainingProfile
from app.services.quiz_sources import (
    QuizSourceError,
    validate_quiz_sources,
)


class QuizGenerationError(Exception):
    """Ошибка генерации банка проверочных вопросов."""


class QuizGenerator:
    def __init__(
        self,
        client: AsyncOpenAI,
        model: str,
        system_prompt: str,
        temperature: float = 0.2,
    ) -> None:
        if not system_prompt.strip():
            raise ValueError("System prompt cannot be empty")

        self.client = client
        self.model = model
        self.system_prompt = system_prompt
        self.temperature = temperature

    async def generate(
        self,
        profile: TrainingProfile,
        material: str,
    ) -> QuizBank:
        if not material.strip():
            raise ValueError("Training material cannot be empty")

        user_prompt = (
            f"Идентификатор профиля: {profile.profile_id}\n"
            f"Версия профиля: {profile.version}\n"
            f"Количество вопросов: {profile.quiz.question_count}\n\n"
            f"Учебный материал:\n{material}"
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": self.system_prompt,
                    },
                    {
                        "role": "user",
                        "content": user_prompt,
                    },
                ],
            )
        except OpenAIError as exc:
            raise QuizGenerationError(
                "AI service is temporarily unavailable"
            ) from exc

        if not response.choices:
            raise QuizGenerationError("AI returned no choices")

        content = response.choices[0].message.content

        if not content:
            raise QuizGenerationError("AI returned an empty response")

        try:
            data = json.loads(content)
            bank = QuizBank.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise QuizGenerationError(
                "AI returned an invalid quiz bank"
            ) from exc

        if bank.profile_id != profile.profile_id:
            raise QuizGenerationError("Generated profile_id mismatch")

        if bank.profile_version != profile.version:
            raise QuizGenerationError("Generated profile version mismatch")

        if len(bank.questions) != profile.quiz.question_count:
            raise QuizGenerationError("Generated question count mismatch")

        try:
            validate_quiz_sources(bank, material)
        except QuizSourceError as exc:
            raise QuizGenerationError(
                "Generated questions contain invalid source excerpts"
            ) from exc

        normalized_sources = [
            " ".join(question.source_excerpt.split()).casefold()
            for question in bank.questions
        ]

        if len(normalized_sources) != len(set(normalized_sources)):
            raise QuizGenerationError(
                "Generated questions contain duplicate source excerpts"
            )

        return bank
