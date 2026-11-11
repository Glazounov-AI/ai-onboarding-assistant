
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import QuizAttempt


class QuizAttemptRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, attempt_id: int) -> QuizAttempt | None:
        return await self.session.get(QuizAttempt, attempt_id)

    async def get_active(
        self, learning_session_id: int
    ) -> QuizAttempt | None:
        statement = select(QuizAttempt).where(
            QuizAttempt.learning_session_id == learning_session_id,
            QuizAttempt.status == "in_progress",
        )
        return await self.session.scalar(statement)

    async def create(
        self,
        learning_session_id: int,
        questions_snapshot: list[dict[str, Any]],
    ) -> QuizAttempt:
        # Блокируем учебную сессию, чтобы параллельные запросы
        # не получили одинаковый номер попытки.
        from app.database.models import LearningSession

        parent = await self.session.scalar(
            select(LearningSession)
            .where(LearningSession.id == learning_session_id)
            .with_for_update()
        )

        if parent is None:
            raise ValueError("Учебная сессия не найдена")

        if parent.status != "testing":
            raise ValueError("Учебная сессия не находится в тестировании")

        if await self.get_active(learning_session_id) is not None:
            raise ValueError("Уже существует активная попытка")

        last_number = await self.session.scalar(
            select(func.max(QuizAttempt.attempt_number)).where(
                QuizAttempt.learning_session_id == learning_session_id
            )
        )

        attempt = QuizAttempt(
            learning_session_id=learning_session_id,
            attempt_number=(last_number or 0) + 1,
            status="in_progress",
            questions_snapshot=questions_snapshot,
        )

        self.session.add(attempt)
        await self.session.flush()
        return attempt

    async def complete(
        self,
        attempt: QuizAttempt,
        score_percent: float,
        passed: bool,
    ) -> QuizAttempt:
        if attempt.status != "in_progress":
            raise ValueError("Попытка уже завершена или отменена")

        if not 0 <= score_percent <= 100:
            raise ValueError("Оценка должна быть от 0 до 100")

        attempt.status = "completed"
        attempt.score_percent = score_percent
        attempt.passed = passed
        attempt.completed_at = datetime.now(UTC)

        await self.session.flush()
        return attempt

    async def cancel(self, attempt: QuizAttempt) -> QuizAttempt:
        if attempt.status != "in_progress":
            raise ValueError("Можно отменить только активную попытку")

        attempt.status = "cancelled"
        attempt.completed_at = datetime.now(UTC)

        await self.session.flush()
        return attempt

    async def get_history(
        self, learning_session_id: int
    ) -> list[QuizAttempt]:
        result = await self.session.scalars(
            select(QuizAttempt)
            .where(QuizAttempt.learning_session_id == learning_session_id)
            .order_by(QuizAttempt.attempt_number)
        )
        return list(result.all())
