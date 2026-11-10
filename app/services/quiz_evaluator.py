from app.core.quiz import QuizResult, QuizSession


class QuizEvaluator:
    @staticmethod
    def evaluate(
        session: QuizSession,
        passing_score_percent: int,
    ) -> QuizResult:
        if not 0 <= passing_score_percent <= 100:
            raise ValueError("Passing score must be between 0 and 100")

        if len(session.answers) != len(session.questions):
            raise ValueError("Cannot evaluate an incomplete quiz")

        correct = sum(
            session.answers[question.question_id] == question.correct_option
            for question in session.questions
        )

        total = len(session.questions)
        score = correct * 100 / total

        return QuizResult(
            total_questions=total,
            correct_answers=correct,
            score_percent=round(score, 2),
            passed=correct * 100 >= passing_score_percent * total,
        )
