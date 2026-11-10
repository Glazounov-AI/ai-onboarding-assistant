
from openai import AsyncOpenAI, OpenAIError


class TutorError(Exception):
    """Ошибка получения ответа от AI-наставника."""


class TutorService:
    def __init__(
        self,
        client: AsyncOpenAI,
        model: str,
        material: str,
        system_prompt: str,
        temperature: float = 0.2,
    ) -> None:
        if not material.strip():
            raise ValueError("Training material cannot be empty")

        if not system_prompt.strip():
            raise ValueError("System prompt cannot be empty")

        self.client = client
        self.model = model
        self.material = material
        self.system_prompt = system_prompt
        self.temperature = temperature

    async def answer(self, question: str) -> str:
        question = question.strip()

        if not question:
            raise ValueError("Question cannot be empty")

        if len(question) > 2000:
            raise ValueError("Question is too long")

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                messages=[
                    {
                        "role": "system",
                        "content": self.system_prompt,
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Учебный материал:\n{self.material}\n\n"
                            f"Вопрос сотрудника:\n{question}"
                        ),
                    },
                ],
            )
        except OpenAIError as exc:
            raise TutorError("AI service is temporarily unavailable") from exc

        if not response.choices:
            raise TutorError("AI service returned no choices")

        answer = response.choices[0].message.content

        if not answer or not answer.strip():
            raise TutorError("AI service returned an empty answer")

        return answer.strip()


