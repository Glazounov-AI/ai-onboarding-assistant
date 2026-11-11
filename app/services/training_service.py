from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.quiz import QuizQuestion, QuizResult, QuizSession
from app.core.session import normalize_employee_name
from app.database.models import Employee, LearningSession
from app.database.repositories.employees import EmployeeRepository
from app.database.repositories.learning_sessions import (
    LearningSessionRepository,
)
from app.database.repositories.quiz_answers import QuizAnswerRepository
from app.database.repositories.quiz_attempts import QuizAttemptRepository
from app.services.quiz_evaluator import QuizEvaluator
from app.services.quiz_session import QuizSessionService


@dataclass(frozen=True)
class AnswerOutcome:
    quiz: QuizSession
    result: QuizResult | None


class TrainingService:
    """Бизнес-логика обучения. Транзакцией управляет вызывающий код."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.employees = EmployeeRepository(session)
        self.learning = LearningSessionRepository(session)
        self.attempts = QuizAttemptRepository(session)
        self.answers = QuizAnswerRepository(session)

    async def start_or_resume(
        self,
        telegram_user_id: int,
        employee_name: str,
        profile_id: str,
        profile_version: int,
        username: str | None = None,
    ) -> LearningSession:
        name = normalize_employee_name(employee_name)

        employee = await self.employees.upsert(
            telegram_user_id=telegram_user_id,
            employee_name=name,
            username=username,
        )

        # Блокируем запись сотрудника до завершения транзакции.
        # Конкурентные запуски одного сотрудника выполняются последовательно.
        await self.session.scalar(
            select(Employee)
            .where(Employee.id == employee.id)
            .with_for_update()
        )

        active = await self.learning.get_active(
            employee.id, profile_id
        )
        if active is not None:
            return active

        return await self.learning.create(
            employee_id=employee.id,
            profile_id=profile_id,
            profile_version=profile_version,
        )

    async def begin_quiz(
        self,
        learning_session_id: int,
        questions: list[QuizQuestion],
    ) -> QuizSession:
        training = await self.session.scalar(
            select(LearningSession)
            .where(LearningSession.id == learning_session_id)
            .with_for_update()
        )

        if training is None:
            raise ValueError("Учебная сессия не найдена")

        if training.status not in ("learning", "testing"):
            raise ValueError("Тестирование недоступно")

        active = await self.attempts.get_active(training.id)

        if active is None:
            if not questions:
                raise ValueError("Список вопросов пуст")

            if training.status == "learning":
                await self.learning.change_status(training, "testing")

            snapshot = [
                question.model_dump(mode="json")
                for question in questions
            ]
            active = await self.attempts.create(training.id, snapshot)

        return await self._restore_quiz(training, active)

    async def restore_quiz(
        self,
        learning_session_id: int,
    ) -> QuizSession | None:
        training = await self.learning.get_by_id(learning_session_id)

        if training is None or training.status != "testing":
            return None

        active = await self.attempts.get_active(training.id)
        if active is None:
            return None

        return await self._restore_quiz(training, active)

    async def submit_answer(
        self,
        learning_session_id: int,
        question_id: str,
        option_index: int,
        passing_score_percent: int,
        expected_attempt_id: int | None = None,
    ) -> AnswerOutcome:
        if not 0 <= passing_score_percent <= 100:
            raise ValueError("Passing score must be between 0 and 100")

        training = await self.session.scalar(
            select(LearningSession)
            .where(LearningSession.id == learning_session_id)
            .with_for_update()
        )

        if training is None or training.status != "testing":
            raise ValueError("Учебная сессия не находится в тестировании")

        attempt = await self.attempts.get_active(training.id)
        if attempt is None:
            raise ValueError("Активная попытка не найдена")

        if (
            expected_attempt_id is not None
            and attempt.id != expected_attempt_id
        ):
            raise ValueError("Кнопка относится к другой попытке тестирования")

        quiz = await self._restore_quiz(training, attempt)

        updated = QuizSessionService.submit_answer(
            quiz, question_id, option_index
        )

        question = next(
            q for q in quiz.questions if q.question_id == question_id
        )

        await self.answers.add_answer(
            attempt_id=attempt.id,
            question_id=question_id,
            selected_option=option_index,
            is_correct=option_index == question.correct_option,
        )

        if not updated.completed:
            return AnswerOutcome(quiz=updated, result=None)

        result = QuizEvaluator.evaluate(
            updated, passing_score_percent
        )

        await self.attempts.complete(
            attempt,
            score_percent=result.score_percent,
            passed=result.passed,
        )

        if result.passed:
            await self.learning.change_status(training, "completed")

        return AnswerOutcome(quiz=updated, result=result)

    async def retry_quiz(
        self,
        learning_session_id: int,
    ) -> QuizSession:
        training = await self.session.scalar(
            select(LearningSession)
            .where(LearningSession.id == learning_session_id)
            .with_for_update()
        )

        if training is None or training.status != "testing":
            raise ValueError("Повторное тестирование недоступно")

        if await self.attempts.get_active(training.id) is not None:
            raise ValueError("Текущая попытка ещё не завершена")

        history = await self.attempts.get_history(training.id)

        if not history:
            raise ValueError("Предыдущая попытка не найдена")

        previous = history[-1]
        if previous.status != "completed" or previous.passed is not False:
            raise ValueError("Повтор разрешён только после неудачной попытки")

        questions = [
            QuizQuestion.model_validate(item)
            for item in previous.questions_snapshot
        ]
        return await self.begin_quiz(training.id, questions)

    async def cancel_training(
        self,
        learning_session_id: int,
    ) -> LearningSession:
        training = await self.session.scalar(
            select(LearningSession)
            .where(LearningSession.id == learning_session_id)
            .with_for_update()
        )

        if training is None:
            raise ValueError("Учебная сессия не найдена")

        active = await self.attempts.get_active(training.id)
        if active is not None:
            await self.attempts.cancel(active)

        return await self.learning.change_status(
            training, "cancelled"
        )

    async def _restore_quiz(
        self,
        training: LearningSession,
        attempt,
    ) -> QuizSession:
        questions = [
            QuizQuestion.model_validate(item)
            for item in attempt.questions_snapshot
        ]

        saved_answers = await self.answers.get_answers(attempt.id)

        return QuizSession(
            profile_id=training.profile_id,
            profile_version=training.profile_version,
            employee_id=training.employee_id,
            questions=questions,
            answers={
                answer.question_id: answer.selected_option
                for answer in saved_answers
            },
        )
