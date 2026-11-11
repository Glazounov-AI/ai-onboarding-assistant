
import logging
from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy.exc import SQLAlchemyError

from app.core.quiz import QuizSession
from app.core.training_profile import TrainingProfile
from app.services.quiz_bank import load_quiz_bank
from app.services.training_service import TrainingService

router = Router()
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DB_ERROR = "Не удалось обратиться к базе данных. Попробуйте позже."


def question_keyboard(
    quiz: QuizSession,
    attempt_id: int,
) -> InlineKeyboardMarkup:
    index = len(quiz.answers)
    question = quiz.questions[index]

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{option_number + 1}. {option}",
                    callback_data=(
                        f"quiz:{attempt_id}:{index}:{option_number}"
                    ),
                )
            ]
            for option_number, option in enumerate(question.options)
        ]
    )


async def send_question(
    message: Message,
    quiz: QuizSession,
    attempt_id: int,
) -> None:
    index = len(quiz.answers)
    question = quiz.questions[index]

    await message.answer(
        f"Вопрос {index + 1} из {len(quiz.questions)}\n\n"
        f"{question.text}",
        reply_markup=question_keyboard(quiz, attempt_id),
    )


async def active_training(service: TrainingService, telegram_id: int, profile_id: str):
    employee = await service.employees.get_by_telegram_id(telegram_id)
    if employee is None:
        return None

    return await service.learning.get_active(employee.id, profile_id)


@router.message(Command("quiz"))
async def start_quiz(
    message: Message,
    training_profile: TrainingProfile,
    session_factory,
) -> None:
    if message.from_user is None:
        return

    quiz = None
    attempt_id = None
    notice = None

    try:
        async with session_factory.begin() as session:
            service = TrainingService(session)
            training = await active_training(
                service, message.from_user.id, training_profile.profile_id
            )

            if training is None:
                notice = "Активного обучения нет. Отправьте /start."
            elif training.status == "testing":
                quiz = await service.restore_quiz(training.id)

                if quiz is None:
                    notice = (
                        "Активной попытки нет. Если тест не сдан, "
                        "используйте /retry."
                    )
            elif training.status == "learning":
                bank = load_quiz_bank(
                    training_profile.quiz.bank_file,
                    training_profile,
                    PROJECT_ROOT,
                )
                quiz = await service.begin_quiz(training.id, bank.questions)
            else:
                notice = "Тестирование сейчас недоступно."

            if quiz is not None:
                attempt = await service.attempts.get_active(training.id)
                if attempt is None:
                    raise ValueError("Не удалось найти активную попытку")
                attempt_id = attempt.id

    except (OSError, ValueError) as exc:
        logger.exception("Cannot start quiz")
        await message.answer(f"Не удалось запустить тест: {exc}")
        return
    except SQLAlchemyError:
        logger.exception("Database error in /quiz")
        await message.answer(DB_ERROR)
        return

    if quiz is None:
        await message.answer(notice or "Не удалось открыть тест.")
        return

    if quiz.completed:
        await message.answer("Эта попытка уже завершена.")
        return

    await send_question(message, quiz, attempt_id)


@router.message(Command("retry"))
async def retry_quiz(
    message: Message,
    training_profile: TrainingProfile,
    session_factory,
) -> None:
    if message.from_user is None:
        return

    if not training_profile.quiz.allow_retry:
        await message.answer("Повторная попытка отключена.")
        return

    quiz = None
    attempt_id = None
    notice = None

    try:
        async with session_factory.begin() as session:
            service = TrainingService(session)
            training = await active_training(
                service, message.from_user.id, training_profile.profile_id
            )

            if training is None:
                notice = "Активного обучения нет. Отправьте /start."
            elif training.status != "testing":
                notice = "Повторная попытка сейчас недоступна."
            else:
                quiz = await service.retry_quiz(training.id)
                attempt = await service.attempts.get_active(training.id)
                if attempt is None:
                    raise ValueError("Новая попытка не найдена")
                attempt_id = attempt.id


    except ValueError as exc:
        await message.answer(str(exc))
        return
    except SQLAlchemyError:
        logger.exception("Database error in /retry")
        await message.answer(DB_ERROR)
        return

    if quiz is None:
        await message.answer(notice or "Не удалось начать повторную попытку.")
        return

    await message.answer("Начинаем повторную попытку.")
    await send_question(message, quiz, attempt_id)


@router.callback_query(F.data.startswith("quiz:"))
async def answer_quiz(
    callback: CallbackQuery,
    training_profile: TrainingProfile,
    session_factory,
) -> None:
    if not isinstance(callback.message, Message):
        await callback.answer("Сообщение недоступно.", show_alert=True)
        return

    try:
        parts = (callback.data or "").split(":")
        if len(parts) != 4 or parts[0] != "quiz":
            raise ValueError("Invalid callback data")

        attempt_id = int(parts[1])
        question_index = int(parts[2])
        option_index = int(parts[3])

        if attempt_id <= 0 or question_index < 0:
            raise ValueError("Invalid callback values")
    except ValueError:
        await callback.answer("Некорректный ответ.", show_alert=True)
        return

    outcome = None
    notice = None
    next_attempt_id = None

    try:
        async with session_factory.begin() as session:
            service = TrainingService(session)
            training = await active_training(
                service, callback.from_user.id, training_profile.profile_id
            )

            if training is None or training.status != "testing":
                notice = "Активный тест не найден."
            else:
                quiz = await service.restore_quiz(training.id)
                active_attempt = await service.attempts.get_active(training.id)

                if quiz is None or active_attempt is None:
                    notice = "Активная попытка не найдена."
                elif active_attempt.id != attempt_id:
                    notice = "Эта кнопка относится к предыдущей попытке."
                elif quiz.completed:
                    notice = "Тест уже завершён."
                elif question_index != len(quiz.answers):
                    notice = "Этот вопрос уже обработан."
                elif not 0 <= option_index < len(
                    quiz.questions[question_index].options
                ):
                    notice = "Недопустимый вариант ответа."
                else:
                    question = quiz.questions[question_index]
                    outcome = await service.submit_answer(
                        learning_session_id=training.id,
                        question_id=question.question_id,
                        option_index=option_index,
                        passing_score_percent=training_profile.quiz.passing_score_percent,
                        expected_attempt_id=attempt_id,
                    )

                    if outcome is not None and outcome.result is None:
                        next_attempt = await service.attempts.get_active(training.id)
                        if next_attempt is None:
                            raise ValueError("Активная попытка исчезла")
                        next_attempt_id = next_attempt.id

    except (ValueError, IndexError) as exc:
        logger.warning("Quiz answer rejected: %s", exc)
        await callback.answer("Ответ не принят.", show_alert=True)
        return
    except SQLAlchemyError:
        logger.exception("Database error while submitting quiz answer")
        await callback.answer("Ошибка базы данных.", show_alert=True)
        return

    if outcome is None:
        await callback.answer(notice or "Ответ не принят.", show_alert=True)
        return

    await callback.answer("Ответ сохранён.")

    # Убираем кнопки у уже обработанного вопроса.
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        logger.warning("Could not remove previous quiz buttons", exc_info=True)

    if outcome.result is not None:
        result = outcome.result
        verdict = (
            "Тест пройден! Обучение завершено."
            if result.passed
            else (
                "Тест пока не пройден. Отправьте /retry."
                if training_profile.quiz.allow_retry
                else "Тест не пройден. Повторная попытка отключена."
            )
        )

        await callback.message.answer(
            f"Результат тестирования\n\n"
            f"Правильных ответов: "
            f"{result.correct_answers} из {result.total_questions}\n"
            f"Результат: {result.score_percent}%\n\n"
            f"{verdict}"
        )
    else:
        await send_question(
            callback.message,
            outcome.quiz,
            next_attempt_id,
        )
