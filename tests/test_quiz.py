import pytest
from pydantic import ValidationError

from app.core.quiz import QuizQuestion, QuizSession
from app.services.quiz_evaluator import QuizEvaluator


def make_question(question_id: str, correct_option: int = 0):
    return QuizQuestion(
        question_id=question_id,
        text=f"Вопрос {question_id}",
        options=["Ответ A", "Ответ B", "Ответ C", "Ответ D"],
        correct_option=correct_option,
    )


def make_session(answers: dict[str, int]):
    return QuizSession(
        profile_id="demo",
        profile_version=1,
        employee_id=123,
        questions=[
            make_question("q1", 0),
            make_question("q2", 1),
            make_question("q3", 2),
            make_question("q4", 3),
        ],
        answers=answers,
    )


def test_all_answers_correct():
    session = make_session(
        {"q1": 0, "q2": 1, "q3": 2, "q4": 3}
    )

    result = QuizEvaluator.evaluate(session, 80)

    assert result.correct_answers == 4
    assert result.score_percent == 100
    assert result.passed is True


def test_passing_score():
    session = make_session(
        {"q1": 0, "q2": 1, "q3": 2, "q4": 0}
    )

    result = QuizEvaluator.evaluate(session, 75)

    assert result.correct_answers == 3
    assert result.score_percent == 75
    assert result.passed is True


def test_failing_score():
    session = make_session(
        {"q1": 0, "q2": 1, "q3": 0, "q4": 0}
    )

    result = QuizEvaluator.evaluate(session, 75)

    assert result.correct_answers == 2
    assert result.passed is False


def test_incomplete_quiz_cannot_be_evaluated():
    session = make_session({"q1": 0})

    with pytest.raises(ValueError, match="incomplete"):
        QuizEvaluator.evaluate(session, 75)


def test_unknown_question_id_rejected():
    with pytest.raises(ValidationError, match="unknown question"):
        make_session({"unknown": 0})


def test_duplicate_options_rejected():
    with pytest.raises(ValidationError, match="unique"):
        QuizQuestion(
            question_id="q1",
            text="Вопрос",
            options=["A", "A", "C", "D"],
            correct_option=0,
        )


def test_duplicate_question_ids_rejected():
    with pytest.raises(ValidationError, match="unique"):
        QuizSession(
            profile_id="demo",
            profile_version=1,
            employee_id=123,
            questions=[make_question("q1"), make_question("q1")],
        )


def test_completed_quiz_requires_all_answers():
    with pytest.raises(ValidationError, match="all answers"):
        QuizSession(
            profile_id="demo",
            profile_version=1,
            employee_id=123,
            questions=[make_question("q1"), make_question("q2")],
            answers={"q1": 0},
            completed=True,
        )
