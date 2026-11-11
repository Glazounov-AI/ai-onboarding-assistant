import pytest
from sqlalchemy.exc import IntegrityError

from app.database.repositories.employees import EmployeeRepository
from app.database.repositories.learning_sessions import (
    LearningSessionRepository,
)


@pytest.fixture
async def employee(db_session):
    repository = EmployeeRepository(db_session)

    return await repository.upsert(
        telegram_user_id=200001,
        employee_name="Тестовый сотрудник",
    )


async def test_create_and_restore(db_session, employee):
    repository = LearningSessionRepository(db_session)

    created = await repository.create(
        employee_id=employee.id,
        profile_id="demo-onboarding",
        profile_version=1,
    )

    restored = await repository.get_active(
        employee.id,
        "demo-onboarding",
    )

    assert restored is not None
    assert restored.id == created.id
    assert restored.status == "learning"


async def test_change_status(db_session, employee):
    repository = LearningSessionRepository(db_session)

    learning_session = await repository.create(
        employee.id, "demo-onboarding", 1
    )

    await repository.change_status(learning_session, "testing")

    assert learning_session.status == "testing"


async def test_complete_session(db_session, employee):
    repository = LearningSessionRepository(db_session)

    learning_session = await repository.create(
        employee.id, "demo-onboarding", 1
    )

    await repository.change_status(learning_session, "completed")

    assert learning_session.completed_at is not None
    assert await repository.get_active(
        employee.id, "demo-onboarding"
    ) is None

    history = await repository.get_history(
        employee.id, "demo-onboarding"
    )

    assert len(history) == 1
    assert history[0].id == learning_session.id


async def test_cancel_and_restart(db_session, employee):
    repository = LearningSessionRepository(db_session)

    first = await repository.create(
        employee.id, "demo-onboarding", 1
    )

    await repository.change_status(first, "cancelled")

    second = await repository.create(
        employee.id, "demo-onboarding", 1
    )

    assert second.id != first.id
    assert second.status == "learning"


async def test_cannot_change_completed_session(db_session, employee):
    repository = LearningSessionRepository(db_session)

    learning_session = await repository.create(
        employee.id, "demo-onboarding", 1
    )

    await repository.change_status(learning_session, "completed")

    with pytest.raises(ValueError):
        await repository.change_status(learning_session, "learning")


async def test_only_one_active_session(db_session, employee):
    repository = LearningSessionRepository(db_session)

    await repository.create(
        employee.id, "demo-onboarding", 1
    )

    with pytest.raises(IntegrityError):
        await repository.create(
            employee.id, "demo-onboarding", 1
        )


async def test_different_profiles(db_session, employee):
    repository = LearningSessionRepository(db_session)

    first = await repository.create(
        employee.id, "demo-onboarding", 1
    )

    second = await repository.create(
        employee.id, "another-course", 1
    )

    assert first.id != second.id
    assert await repository.get_active(
        employee.id, "another-course"
    ) is not None