import asyncio
import uuid

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.quiz import QuizQuestion
from app.database.models import (
    Employee,
    LearningSession,
    QuizAnswer,
    QuizAttempt,
)
from app.services.quiz_session import QuizSessionError
from app.services.training_service import TrainingService
from tests.db_helpers import verified_test_engine


@pytest.mark.asyncio
async def test_concurrent_answers_only_one_is_saved():
    engine = await verified_test_engine()
    factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    employee_id = None
    training_id = None
    attempt_id = None

    questions = [
        QuizQuestion(
            question_id="q1",
            text="Первый вопрос",
            options=["A", "B", "C", "D"],
            correct_option=1,
        ),
        QuizQuestion(
            question_id="q2",
            text="Второй вопрос",
            options=["A", "B", "C", "D"],
            correct_option=2,
        ),
    ]

    try:
        # Создаём уникального сотрудника и учебную сессию.
        unique_id = uuid.uuid4().int % (10**12) + 10**12

        async with factory.begin() as session:
            service = TrainingService(session)

            training = await service.start_or_resume(
                telegram_user_id=unique_id,
                employee_name="Конкурентный тест",
                profile_id="concurrency-test",
                profile_version=1,
            )
            training_id = training.id
            employee_id = training.employee_id

            await service.begin_quiz(
                training.id,
                questions,
            )

            attempt = await service.attempts.get_active(
                training.id
            )
            assert attempt is not None
            attempt_id = attempt.id

        async def submit(option_index: int):
            async with factory.begin() as session:
                service = TrainingService(session)
                return await service.submit_answer(
                    learning_session_id=training_id,
                    question_id="q1",
                    option_index=option_index,
                    passing_score_percent=80,
                    expected_attempt_id=attempt_id,
                )

        # Оба запроса используют отдельные транзакции.
        results = await asyncio.wait_for(
            asyncio.gather(
                submit(1),
                submit(2),
                return_exceptions=True,
            ),
            timeout=15,
        )

        successes = [
            item for item in results
            if not isinstance(item, BaseException)
        ]
        errors = [
            item for item in results
            if isinstance(item, BaseException)
        ]

        assert len(successes) == 1, f"Результаты: {results!r}"
        assert len(errors) == 1, f"Результаты: {results!r}"

        assert isinstance(errors[0], QuizSessionError), (
            f"Ожидали QuizSessionError, получили "
            f"{type(errors[0]).__name__}: {errors[0]!r}"
        )

        assert "already answered" in str(errors[0]), (
            f"Неожиданный текст ошибки: {errors[0]!r}"
        )

        # Проверяем фактическое состояние PostgreSQL.
        async with factory() as session:
            count = await session.scalar(
                select(func.count(QuizAnswer.id)).where(
                    QuizAnswer.attempt_id == attempt_id,
                    QuizAnswer.question_id == "q1",
                )
            )

        assert count == 1

    finally:
        # Удаляем только данные этого теста.
        try:
            if employee_id is not None:
                async with factory.begin() as session:
                    if attempt_id is not None:
                        await session.execute(
                            delete(QuizAnswer).where(
                                QuizAnswer.attempt_id == attempt_id
                            )
                        )

                    if training_id is not None:
                        await session.execute(
                            delete(QuizAttempt).where(
                                QuizAttempt.learning_session_id
                                == training_id
                            )
                        )
                        await session.execute(
                            delete(LearningSession).where(
                                LearningSession.id == training_id
                            )
                        )

                    await session.execute(
                        delete(Employee).where(
                            Employee.id == employee_id
                        )
                    )
        finally:
            await engine.dispose()
