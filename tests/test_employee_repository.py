import asyncio
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.database.repositories.employees import EmployeeRepository
from tests.db_helpers import verified_test_engine


@pytest.mark.asyncio
async def test_create_employee(db_session):
    repository = EmployeeRepository(db_session)

    employee = await repository.upsert(
        telegram_user_id=100001,
        employee_name="Иван Петров",
        username="ivan_test",
    )

    assert employee.id is not None
    assert employee.telegram_user_id == 100001
    assert employee.employee_name == "Иван Петров"
    assert employee.username == "ivan_test"


@pytest.mark.asyncio
async def test_get_employee_by_telegram_id(db_session):
    repository = EmployeeRepository(db_session)

    await repository.upsert(
        telegram_user_id=100002,
        employee_name="Анна Смирнова",
    )

    employee = await repository.get_by_telegram_id(100002)

    assert employee is not None
    assert employee.employee_name == "Анна Смирнова"


@pytest.mark.asyncio
async def test_upsert_does_not_create_duplicate(db_session):
    repository = EmployeeRepository(db_session)

    first = await repository.upsert(
        telegram_user_id=100003,
        employee_name="Иван Петров",
    )

    second = await repository.upsert(
        telegram_user_id=100003,
        employee_name="Иван Сидоров",
    )

    assert first.id == second.id
    assert second.employee_name == "Иван Сидоров"


@pytest.mark.asyncio
async def test_unknown_employee_returns_none(db_session):
    repository = EmployeeRepository(db_session)

    employee = await repository.get_by_telegram_id(999999999)

    assert employee is None


@pytest.mark.asyncio
async def test_concurrent_upsert_does_not_create_duplicates():

    engine = await verified_test_engine()
    telegram_user_id = uuid.uuid4().int % (2**62) + 2**62

    try:
        # Проверяем фактическую базу до любых изменений.
        async with engine.connect() as connection:
            database_name = await connection.scalar(
                text("SELECT current_database()")
            )
            assert database_name == "onboarding_test"

        async def register(name: str) -> int:
            async with async_sessionmaker(
                engine,
                expire_on_commit=False,
            )() as session:
                repository = EmployeeRepository(session)

                employee = await repository.upsert(
                    telegram_user_id=telegram_user_id,
                    employee_name=name,
                )

                employee_id = employee.id
                await session.commit()
                return employee_id

        first_id, second_id = await asyncio.gather(
            register("Иван Петров"),
            register("Иван Сидоров"),
        )

        assert first_id == second_id

        async with engine.connect() as connection:
            count = await connection.scalar(
                text(
                    "SELECT COUNT(*) FROM employees "
                    "WHERE telegram_user_id = :telegram_user_id"
                ),
                {"telegram_user_id": telegram_user_id},
            )

            assert count == 1

    finally:
        try:
            # Удаляем только запись, созданную конкурентным тестом.
            async with engine.begin() as connection:
                database_name = await connection.scalar(
                    text("SELECT current_database()")
                )

                if database_name != "onboarding_test":
                    raise RuntimeError(
                        "Очистка разрешена только в onboarding_test"
                    )

                await connection.execute(
                    text(
                        "DELETE FROM employees "
                        "WHERE telegram_user_id = :telegram_user_id"
                    ),
                    {"telegram_user_id": telegram_user_id},
                )
        finally:
            await engine.dispose()