
import pytest

from app.core.quiz import QuizQuestion
from app.database.repositories.quiz_attempts import QuizAttemptRepository
from app.services.training_service import TrainingService


@pytest.fixture
def questions():
    return [
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


@pytest.fixture
async def training(db_session):
    service = TrainingService(db_session)
    return await service.start_or_resume(
        telegram_user_id=400001,
        employee_name="Иван Петров",
        profile_id="demo-onboarding",
        profile_version=1,
    )


async def test_start_and_resume(db_session):
    service = TrainingService(db_session)

    first = await service.start_or_resume(
        400002, "Иван Петров", "demo-onboarding", 1
    )
    second = await service.start_or_resume(
        400002, "Иван Петров", "demo-onboarding", 1
    )

    assert first.id == second.id


async def test_begin_and_restore_quiz(
    db_session, training, questions
):
    service = TrainingService(db_session)

    started = await service.begin_quiz(training.id, questions)
    restored = await service.restore_quiz(training.id)

    assert restored is not None
    assert len(started.questions) == 2
    assert restored.questions == started.questions


async def test_resume_quiz_does_not_duplicate_attempt(
    db_session, training, questions
):
    service = TrainingService(db_session)

    await service.begin_quiz(training.id, questions)
    await service.begin_quiz(training.id, questions)

    history = await QuizAttemptRepository(
        db_session
    ).get_history(training.id)

    assert len(history) == 1


async def test_save_and_restore_answer(
    db_session, training, questions
):
    service = TrainingService(db_session)
    await service.begin_quiz(training.id, questions)

    outcome = await service.submit_answer(
        training.id, "q1", 1, 80
    )
    restored = await service.restore_quiz(training.id)

    assert outcome.result is None
    assert restored is not None
    assert restored.answers == {"q1": 1}


async def test_passed_quiz_completes_training(
    db_session, training, questions
):
    service = TrainingService(db_session)
    await service.begin_quiz(training.id, questions)

    await service.submit_answer(training.id, "q1", 1, 80)
    outcome = await service.submit_answer(
        training.id, "q2", 2, 80
    )

    assert outcome.result is not None
    assert outcome.result.passed is True
    assert outcome.result.score_percent == 100

    saved = await service.learning.get_by_id(training.id)
    assert saved.status == "completed"


async def test_failed_quiz_allows_retry(
    db_session, training, questions
):
    service = TrainingService(db_session)
    await service.begin_quiz(training.id, questions)

    await service.submit_answer(training.id, "q1", 0, 80)
    outcome = await service.submit_answer(
        training.id, "q2", 2, 80
    )

    assert outcome.result is not None
    assert outcome.result.passed is False

    retried = await service.retry_quiz(training.id)

    assert retried.answers == {}

    history = await service.attempts.get_history(training.id)
    assert [item.attempt_number for item in history] == [1, 2]


async def test_cancel_training(
    db_session, training, questions
):
    service = TrainingService(db_session)
    await service.begin_quiz(training.id, questions)

    cancelled = await service.cancel_training(training.id)

    assert cancelled.status == "cancelled"
    assert await service.restore_quiz(training.id) is None


async def test_reject_duplicate_answer(
    db_session, training, questions
):
    service = TrainingService(db_session)
    await service.begin_quiz(training.id, questions)

    await service.submit_answer(training.id, "q1", 1, 80)

    with pytest.raises(Exception, match="already answered"):
        await service.submit_answer(training.id, "q1", 2, 80)


async def test_reject_answer_from_previous_attempt(
    db_session, training, questions
):
    service = TrainingService(db_session)
    await service.begin_quiz(training.id, questions)

    first_attempt = await service.attempts.get_active(training.id)
    assert first_attempt is not None
    first_attempt_id = first_attempt.id

    await service.submit_answer(training.id, "q1", 0, 80)
    await service.submit_answer(training.id, "q2", 0, 80)

    await service.retry_quiz(training.id)

    second_attempt = await service.attempts.get_active(training.id)
    assert second_attempt is not None
    assert second_attempt.id != first_attempt_id

    with pytest.raises(ValueError, match="другой попытке"):
        await service.submit_answer(
            learning_session_id=training.id,
            question_id="q1",
            option_index=1,
            passing_score_percent=80,
            expected_attempt_id=first_attempt_id,
        )

    restored = await service.restore_quiz(training.id)
    assert restored is not None
    assert restored.answers == {}


async def test_accept_answer_for_current_attempt(
    db_session, training, questions
):
    service = TrainingService(db_session)
    await service.begin_quiz(training.id, questions)

    attempt = await service.attempts.get_active(training.id)
    assert attempt is not None

    outcome = await service.submit_answer(
        learning_session_id=training.id,
        question_id="q1",
        option_index=1,
        passing_score_percent=80,
        expected_attempt_id=attempt.id,
    )

    assert outcome.quiz.answers == {"q1": 1}


async def test_reject_answer_after_cancel(
    db_session, training, questions
):
    service = TrainingService(db_session)
    await service.begin_quiz(training.id, questions)

    attempt = await service.attempts.get_active(training.id)
    assert attempt is not None

    await service.cancel_training(training.id)

    with pytest.raises(ValueError, match="не находится в тестировании"):
        await service.submit_answer(
            learning_session_id=training.id,
            question_id="q1",
            option_index=1,
            passing_score_percent=80,
            expected_attempt_id=attempt.id,
        )


async def test_retry_preserves_question_order(
    db_session, training, questions
):
    service = TrainingService(db_session)
    await service.begin_quiz(training.id, questions)

    await service.submit_answer(training.id, "q1", 0, 80)
    await service.submit_answer(training.id, "q2", 0, 80)

    retried = await service.retry_quiz(training.id)

    assert [
        question.question_id for question in retried.questions
    ] == ["q1", "q2"]
    assert retried.answers == {}
