
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import QuizAnswer, QuizAttempt


class QuizAnswerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_answer(
        self,
        attempt_id: int,
        question_id: str,
        selected_option: int,
        is_correct: bool,
    ) -> QuizAnswer:
        if not 0 <= selected_option <= 3:
            raise ValueError("Вариант ответа должен быть от 0 до 3")

        attempt = await self.session.scalar(
            select(QuizAttempt)
            .where(QuizAttempt.id == attempt_id)
            .with_for_update()
        )

        if attempt is None:
            raise ValueError("Попытка не найдена")

        if attempt.status != "in_progress":
            raise ValueError("Нельзя отвечать в завершённой попытке")

        question_ids = {
            question["question_id"]
            for question in attempt.questions_snapshot
        }
        if question_id not in question_ids:
            raise ValueError("Вопрос отсутствует в сохранённом тесте")

        existing = await self.session.scalar(
            select(QuizAnswer).where(
                QuizAnswer.attempt_id == attempt_id,
                QuizAnswer.question_id == question_id,
            )
        )
        if existing is not None:
            raise ValueError("На этот вопрос уже дан ответ")

        answer = QuizAnswer(
            attempt_id=attempt_id,
            question_id=question_id,
            selected_option=selected_option,
            is_correct=is_correct,
        )
        self.session.add(answer)
        await self.session.flush()
        return answer

    async def get_answers(self, attempt_id: int) -> list[QuizAnswer]:
        result = await self.session.scalars(
            select(QuizAnswer)
            .where(QuizAnswer.attempt_id == attempt_id)
            .order_by(QuizAnswer.id)
        )
        return list(result.all())
