import pytest

from app.core.quiz import QuizQuestion, QuizSession
from app.services.quiz_session import QuizSessionError, QuizSessionService


def make_session():
    return QuizSession(
        profile_id="demo",
        profile_version=1,
        employee_id=123,
        questions=[
            QuizQuestion(
                question_id="q1",
                text="Первый вопрос",
                options=["A", "B", "C", "D"],
                correct_option=0,
            ),
            QuizQuestion(
                question_id="q2",
                text="Второй вопрос",
                options=["A", "B", "C", "D"],
                correct_option=1,
            ),
        ],
    )


def test_submit_answer():
    session = make_session()

    updated = QuizSessionService.submit_answer(session, "q1", 0)

    assert updated.answers == {"q1": 0}
    assert updated.completed is False
    assert session.answers == {}


def test_last_answer_completes_quiz():
    session = make_session()

    session = QuizSessionService.submit_answer(session, "q1", 0)
    session = QuizSessionService.submit_answer(session, "q2", 1)

    assert session.completed is True
    assert len(session.answers) == 2


def test_duplicate_answer_rejected():
    session = make_session()
    session = QuizSessionService.submit_answer(session, "q1", 0)

    with pytest.raises(QuizSessionError, match="already answered"):
        QuizSessionService.submit_answer(session, "q1", 1)


def test_unknown_question_rejected():
    with pytest.raises(QuizSessionError, match="Unknown question"):
        QuizSessionService.submit_answer(make_session(), "q99", 0)


def test_invalid_option_rejected():
    with pytest.raises(QuizSessionError, match="Invalid answer"):
        QuizSessionService.submit_answer(make_session(), "q1", 4)


def test_completed_quiz_rejected():
    session = make_session()
    session = QuizSessionService.submit_answer(session, "q1", 0)
    session = QuizSessionService.submit_answer(session, "q2", 1)

    with pytest.raises(QuizSessionError, match="already completed"):
        QuizSessionService.submit_answer(session, "q1", 0)
