import uuid

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.quiz import QuizQuestion
from app.database.models import (
    Employee,
    LearningSession,
    QuizAnswer,
    QuizAttempt,
)
from app.services.training_service import TrainingService
from tests.db_helpers import verified_test_engine


@pytest.mark.asyncio
async def test_quiz_restores_after_new_database_connection():
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
        # Этап 1. Создаём обучение и начинаем тест.
        telegram_id = uuid.uuid4().int % (10**12) + 10**12

        async with factory.begin() as session:
            service = TrainingService(session)

            training = await service.start_or_resume(
                telegram_user_id=telegram_id,
                employee_name="Тест восстановления",
                profile_id="persistence-test",
                profile_version=1,
            )

            employee_id = training.employee_id
            training_id = training.id

            await service.begin_quiz(training_id, questions)

            attempt = await service.attempts.get_active(
                training_id
            )
            assert attempt is not None
            attempt_id = attempt.id

            await service.submit_answer(
                learning_session_id=training_id,
                question_id="q1",
                option_index=1,
                passing_score_percent=80,
                expected_attempt_id=attempt_id,
            )

        # Транзакция завершена, первая сессия закрыта.

        # Этап 2. Открываем новую сессию PostgreSQL.
        async with factory.begin() as session:
            service = TrainingService(session)

            restored = await service.restore_quiz(training_id)

            assert restored is not None
            assert restored.answers == {"q1": 1}
            assert [q.question_id for q in restored.questions] == [
                "q1",
                "q2",
            ]

            active = await service.attempts.get_active(
                training_id
            )
            assert active is not None
            assert active.id == attempt_id

            history = await service.attempts.get_history(
                training_id
            )
            assert len(history) == 1

            # Продолжаем с того места, где остановились.
            outcome = await service.submit_answer(
                learning_session_id=training_id,
                question_id="q2",
                option_index=2,
                passing_score_percent=80,
                expected_attempt_id=attempt_id,
            )

            assert outcome.result is not None
            assert outcome.result.passed is True
            assert outcome.result.score_percent == 100

        # Этап 3. Проверяем итог в новой сессии.
        async with factory() as session:
            service = TrainingService(session)

            saved = await service.learning.get_by_id(
                training_id
            )
            assert saved is not None
            assert saved.status == "completed"

            history = await service.attempts.get_history(
                training_id
            )
            assert len(history) == 1
            assert history[0].status == "completed"

    finally:
        # Удаляем только записи, созданные этим тестом.
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
