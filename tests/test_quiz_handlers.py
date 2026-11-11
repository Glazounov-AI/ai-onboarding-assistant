from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.types import Message

from app.bot.handlers.quiz import (
    active_training,
    answer_quiz,
    question_keyboard,
    send_question,
)


def make_quiz():
    question = SimpleNamespace(
        question_id="q1",
        text="Что означает API?",
        options=["Вариант A", "Вариант B", "Вариант C", "Вариант D"],
    )
    return SimpleNamespace(
        questions=[question],
        answers={},
        completed=False,
    )


def make_callback(data: str):
    message = MagicMock(spec=Message)
    message.answer = AsyncMock()
    message.edit_reply_markup = AsyncMock()

    return SimpleNamespace(
        message=message,
        data=data,
        from_user=SimpleNamespace(id=123),
        answer=AsyncMock(),
    )


def make_session_factory():
    session = MagicMock()
    transaction = MagicMock()
    transaction.__aenter__ = AsyncMock(return_value=session)
    transaction.__aexit__ = AsyncMock(return_value=False)

    factory = MagicMock()
    factory.begin.return_value = transaction
    return factory


def make_training_service(
    *,
    training_status="testing",
    attempt_id=15,
    answered=False,
):
    quiz = make_quiz()

    if answered:
        quiz.answers = {"q1": 1}

    training = SimpleNamespace(
        id=7,
        status=training_status,
    )

    service = MagicMock()
    service.employees.get_by_telegram_id = AsyncMock(
        return_value=SimpleNamespace(id=5)
    )
    service.learning.get_active = AsyncMock(
        return_value=training
        if training_status != "cancelled"
        else None
    )
    service.restore_quiz = AsyncMock(return_value=quiz)
    service.attempts.get_active = AsyncMock(
        return_value=SimpleNamespace(id=attempt_id)
    )
    service.submit_answer = AsyncMock()

    return service


def test_question_keyboard_has_four_options():
    keyboard = question_keyboard(make_quiz(), attempt_id=15)

    assert len(keyboard.inline_keyboard) == 4
    assert [
        row[0].callback_data
        for row in keyboard.inline_keyboard
    ] == [
        "quiz:15:0:0",
        "quiz:15:0:1",
        "quiz:15:0:2",
        "quiz:15:0:3",
    ]


@pytest.mark.asyncio
async def test_send_question():
    message = SimpleNamespace(answer=AsyncMock())

    await send_question(message, make_quiz(), attempt_id=15)

    message.answer.assert_awaited_once()
    args, kwargs = message.answer.await_args
    assert "Вопрос 1 из 1" in args[0]
    assert "Что означает API?" in args[0]
    assert kwargs["reply_markup"] is not None
    assert (
        kwargs["reply_markup"].inline_keyboard[0][0].callback_data
        == "quiz:15:0:0"
    )


@pytest.mark.asyncio
async def test_active_training_for_unknown_employee():
    service = SimpleNamespace(
        employees=SimpleNamespace(
            get_by_telegram_id=AsyncMock(return_value=None)
        ),
        learning=SimpleNamespace(get_active=AsyncMock()),
    )

    result = await active_training(service, 123, "demo")

    assert result is None
    service.learning.get_active.assert_not_awaited()


@pytest.mark.asyncio
async def test_active_training_for_existing_employee():
    training = SimpleNamespace(id=7, status="learning")
    service = SimpleNamespace(
        employees=SimpleNamespace(
            get_by_telegram_id=AsyncMock(
                return_value=SimpleNamespace(id=5)
            )
        ),
        learning=SimpleNamespace(
            get_active=AsyncMock(return_value=training)
        ),
    )

    result = await active_training(service, 123, "demo")

    assert result is training
    service.learning.get_active.assert_awaited_once_with(5, "demo")


@pytest.mark.asyncio
async def test_answer_quiz_rejects_unavailable_message():
    callback = SimpleNamespace(
        message=None,
        data="quiz:15:0:1",
        answer=AsyncMock(),
    )

    await answer_quiz(
        callback,
        training_profile=SimpleNamespace(),
        session_factory=None,
    )

    callback.answer.assert_awaited_once_with(
        "Сообщение недоступно.",
        show_alert=True,
    )


@pytest.mark.asyncio
async def test_reject_callback_from_previous_attempt():
    callback = make_callback("quiz:14:0:1")
    service = make_training_service(attempt_id=15)

    with patch(
        "app.bot.handlers.quiz.TrainingService",
        return_value=service,
    ):
        await answer_quiz(
            callback,
            training_profile=SimpleNamespace(
                profile_id="demo-onboarding"
            ),
            session_factory=make_session_factory(),
        )

    service.submit_answer.assert_not_awaited()
    callback.answer.assert_awaited_once_with(
        "Эта кнопка относится к предыдущей попытке.",
        show_alert=True,
    )


@pytest.mark.asyncio
async def test_reject_callback_for_answered_question():
    callback = make_callback("quiz:15:0:2")
    service = make_training_service(
        attempt_id=15,
        answered=True,
    )

    with patch(
        "app.bot.handlers.quiz.TrainingService",
        return_value=service,
    ):
        await answer_quiz(
            callback,
            training_profile=SimpleNamespace(
                profile_id="demo-onboarding"
            ),
            session_factory=make_session_factory(),
        )

    service.submit_answer.assert_not_awaited()
    callback.answer.assert_awaited_once_with(
        "Этот вопрос уже обработан.",
        show_alert=True,
    )


@pytest.mark.asyncio
async def test_reject_callback_after_training_cancelled():
    callback = make_callback("quiz:15:0:1")
    service = make_training_service(
        training_status="cancelled",
    )

    with patch(
        "app.bot.handlers.quiz.TrainingService",
        return_value=service,
    ):
        await answer_quiz(
            callback,
            training_profile=SimpleNamespace(
                profile_id="demo-onboarding"
            ),
            session_factory=make_session_factory(),
        )

    service.submit_answer.assert_not_awaited()
    callback.answer.assert_awaited_once_with(
        "Активный тест не найден.",
        show_alert=True,
    )
