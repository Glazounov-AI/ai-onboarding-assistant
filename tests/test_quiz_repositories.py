
import pytest

from app.database.repositories.employees import EmployeeRepository
from app.database.repositories.learning_sessions import (
    LearningSessionRepository,
)
from app.database.repositories.quiz_answers import QuizAnswerRepository
from app.database.repositories.quiz_attempts import QuizAttemptRepository

QUESTIONS = [
    {"question_id": "q1", "text": "Первый вопрос"},
    {"question_id": "q2", "text": "Второй вопрос"},
]


@pytest.fixture
async def learning_session(db_session):
    employees = EmployeeRepository(db_session)
    sessions = LearningSessionRepository(db_session)

    employee = await employees.upsert(
        telegram_user_id=300001,
        employee_name="Сотрудник для тестирования",
    )

    training = await sessions.create(
        employee_id=employee.id,
        profile_id="demo-onboarding",
        profile_version=1,
    )
    await sessions.change_status(training, "testing")
    return training


async def test_create_attempt(db_session, learning_session):
    repo = QuizAttemptRepository(db_session)

    attempt = await repo.create(learning_session.id, QUESTIONS)

    assert attempt.id is not None
    assert attempt.attempt_number == 1
    assert attempt.questions_snapshot == QUESTIONS
    assert attempt.status == "in_progress"


async def test_restore_active_attempt(db_session, learning_session):
    repo = QuizAttemptRepository(db_session)
    created = await repo.create(learning_session.id, QUESTIONS)

    restored = await repo.get_active(learning_session.id)

    assert restored is not None
    assert restored.id == created.id


async def test_prevent_second_active_attempt(
    db_session, learning_session
):
    repo = QuizAttemptRepository(db_session)
    await repo.create(learning_session.id, QUESTIONS)

    with pytest.raises(ValueError, match="активная попытка"):
        await repo.create(learning_session.id, QUESTIONS)


async def test_complete_attempt(db_session, learning_session):
    repo = QuizAttemptRepository(db_session)
    attempt = await repo.create(learning_session.id, QUESTIONS)

    await repo.complete(attempt, score_percent=100, passed=True)

    assert attempt.status == "completed"
    assert attempt.score_percent == 100
    assert attempt.passed is True
    assert attempt.completed_at is not None
    assert await repo.get_active(learning_session.id) is None


async def test_retry_increments_number(db_session, learning_session):
    repo = QuizAttemptRepository(db_session)

    first = await repo.create(learning_session.id, QUESTIONS)
    await repo.complete(first, score_percent=50, passed=False)

    second = await repo.create(learning_session.id, QUESTIONS)

    assert second.attempt_number == 2
    assert second.id != first.id

    history = await repo.get_history(learning_session.id)
    assert [item.attempt_number for item in history] == [1, 2]


async def test_cancel_attempt(db_session, learning_session):
    repo = QuizAttemptRepository(db_session)

    attempt = await repo.create(learning_session.id, QUESTIONS)
    await repo.cancel(attempt)

    assert attempt.status == "cancelled"
    assert attempt.completed_at is not None


async def test_reject_invalid_score(db_session, learning_session):
    repo = QuizAttemptRepository(db_session)
    attempt = await repo.create(learning_session.id, QUESTIONS)

    with pytest.raises(ValueError):
        await repo.complete(attempt, score_percent=110, passed=True)


async def test_save_answers(db_session, learning_session):
    attempts = QuizAttemptRepository(db_session)
    answers = QuizAnswerRepository(db_session)

    attempt = await attempts.create(learning_session.id, QUESTIONS)

    await answers.add_answer(attempt.id, "q1", 2, True)
    await answers.add_answer(attempt.id, "q2", 1, False)

    saved = await answers.get_answers(attempt.id)

    assert len(saved) == 2
    assert saved[0].question_id == "q1"
    assert saved[0].selected_option == 2
    assert saved[0].is_correct is True
    assert saved[1].is_correct is False


async def test_reject_duplicate_answer(db_session, learning_session):
    attempts = QuizAttemptRepository(db_session)
    answers = QuizAnswerRepository(db_session)

    attempt = await attempts.create(learning_session.id, QUESTIONS)
    await answers.add_answer(attempt.id, "q1", 0, True)

    with pytest.raises(ValueError, match="уже дан ответ"):
        await answers.add_answer(attempt.id, "q1", 1, False)


async def test_reject_unknown_question(db_session, learning_session):
    attempts = QuizAttemptRepository(db_session)
    answers = QuizAnswerRepository(db_session)

    attempt = await attempts.create(learning_session.id, QUESTIONS)

    with pytest.raises(ValueError, match="отсутствует"):
        await answers.add_answer(attempt.id, "unknown", 0, False)


async def test_reject_answer_after_completion(
    db_session, learning_session
):
    attempts = QuizAttemptRepository(db_session)
    answers = QuizAnswerRepository(db_session)

    attempt = await attempts.create(learning_session.id, QUESTIONS)
    await attempts.complete(attempt, 100, True)

    with pytest.raises(ValueError, match="завершённой"):
        await answers.add_answer(attempt.id, "q1", 0, True)


async def test_reject_attempt_when_not_testing(
    db_session, learning_session
):
    sessions = LearningSessionRepository(db_session)
    attempts = QuizAttemptRepository(db_session)

    await sessions.change_status(learning_session, "completed")

    with pytest.raises(ValueError, match="не находится"):
        await attempts.create(learning_session.id, QUESTIONS)
