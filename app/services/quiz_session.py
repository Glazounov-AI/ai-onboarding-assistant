from app.core.quiz import QuizSession


class QuizSessionError(Exception):
    """Ошибка прохождения тестирования."""


class QuizSessionService:
    @staticmethod
    def submit_answer(
        session: QuizSession,
        question_id: str,
        option_index: int,
    ) -> QuizSession:
        if session.completed:
            raise QuizSessionError("Quiz is already completed")

        if not 0 <= option_index <= 3:
            raise QuizSessionError("Invalid answer option")

        question_ids = {q.question_id for q in session.questions}

        if question_id not in question_ids:
            raise QuizSessionError("Unknown question")

        if question_id in session.answers:
            raise QuizSessionError("Question already answered")

        next_answers = {
            **session.answers,
            question_id: option_index,
        }

        return session.model_copy(
            update={
                "answers": next_answers,
                "completed": len(next_answers) == len(session.questions),
            }
        )
