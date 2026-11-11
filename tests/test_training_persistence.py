
import asyncio
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.quiz import QuizQuestion
from app.services.training_service import TrainingService
from tests.db_helpers import verified_test_engine

PROFILE = "persistence-test"


@pytest.fixture
async def database():
    engine = await verified_test_engine()
    telegram_id = uuid.uuid4().int % (2**62) + 2**62

    try:
        yield engine, telegram_id
    finally:
        # Очистка только тестовых данных, созданных этой фикстурой.
        try:
            async with engine.begin() as connection:
                actual_db = await connection.scalar(
                    text("SELECT current_database()")
                )
                if actual_db != "onboarding_test":
                    raise RuntimeError("Очистка вне тестовой БД запрещена")

                params = {"telegram_id": telegram_id}

                await connection.execute(
                    text("""
                        DELETE FROM quiz_answers
                        WHERE attempt_id IN (
                            SELECT qa.id FROM quiz_attempts qa
                            JOIN learning_sessions ls
                              ON qa.learning_session_id = ls.id
                            JOIN employees e ON ls.employee_id = e.id
                            WHERE e.telegram_user_id = :telegram_id
                        )
                    """),
                    params,
                )
                await connection.execute(
                    text("""
                        DELETE FROM quiz_attempts
                        WHERE learning_session_id IN (
                            SELECT ls.id FROM learning_sessions ls
                            JOIN employees e ON ls.employee_id = e.id
                            WHERE e.telegram_user_id = :telegram_id
                        )
                    """),
                    params,
                )
                await connection.execute(
                    text("""
                        DELETE FROM learning_sessions
                        WHERE employee_id IN (
                            SELECT id FROM employees
                            WHERE telegram_user_id = :telegram_id
                        )
                    """),
                    params,
                )
                await connection.execute(
                    text("""
                        DELETE FROM employees
                        WHERE telegram_user_id = :telegram_id
                    """),
                    params,
                )
        finally:
            await engine.dispose()


def make_questions():
    return [
        QuizQuestion(
            question_id="q1",
            text="Проверочный вопрос",
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


async def start_training(factory, telegram_id):
    async with factory() as session:
        service = TrainingService(session)
        training = await service.start_or_resume(
            telegram_user_id=telegram_id,
            employee_name="Тестовый сотрудник",
            profile_id=PROFILE,
            profile_version=1,
        )
        training_id = training.id
        await session.commit()
        return training_id


async def test_restore_after_new_connection(database):
    engine, telegram_id = database
    factory = async_sessionmaker(
        engine, expire_on_commit=False
    )

    training_id = await start_training(factory, telegram_id)

    async with factory() as session:
        service = TrainingService(session)
        await service.begin_quiz(training_id, make_questions())
        await service.submit_answer(training_id, "q1", 1, 80)
        await session.commit()

    # Закрываем первое подключение и создаём новый engine.
    await engine.dispose()
    second_engine = await verified_test_engine()

    try:
        second_factory = async_sessionmaker(
            second_engine, expire_on_commit=False
        )

        async with second_factory() as session:
            service = TrainingService(session)
            restored = await service.restore_quiz(training_id)

            assert restored is not None
            assert restored.answers == {"q1": 1}
            assert len(restored.questions) == 2

            resumed = await service.start_or_resume(
                telegram_id, "Тестовый сотрудник", PROFILE, 1
            )
            assert resumed.id == training_id
    finally:
        await second_engine.dispose()


async def test_rollback_discards_changes(database):
    engine, telegram_id = database
    factory = async_sessionmaker(
        engine, expire_on_commit=False
    )

    async with factory() as session:
        service = TrainingService(session)
        training = await service.start_or_resume(
            telegram_id, "Тестовый сотрудник", PROFILE, 1
        )
        rolled_back_id = training.id
        await session.rollback()

    async with factory() as session:
        service = TrainingService(session)
        employee = await service.employees.get_by_telegram_id(
            telegram_id
        )

        assert employee is None

        training = await service.learning.get_by_id(
            rolled_back_id
        )
        assert training is None


async def test_concurrent_start_creates_one_session(database):
    engine, telegram_id = database
    factory = async_sessionmaker(
        engine, expire_on_commit=False
    )

    async def start():
        return await start_training(factory, telegram_id)

    first_id, second_id = await asyncio.wait_for(
        asyncio.gather(start(), start()),
        timeout=15,
    )

    assert first_id == second_id

    async with engine.connect() as connection:
        count = await connection.scalar(
            text("""
                SELECT COUNT(*)
                FROM learning_sessions ls
                JOIN employees e ON e.id = ls.employee_id
                WHERE e.telegram_user_id = :telegram_id
                  AND ls.profile_id = :profile_id
                  AND ls.status IN (
                      'waiting_for_name', 'learning', 'testing'
                  )
            """),
            {
                "telegram_id": telegram_id,
                "profile_id": PROFILE,
            },
        )

        assert count == 1
