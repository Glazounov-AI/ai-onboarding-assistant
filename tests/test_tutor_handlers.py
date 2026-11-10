
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.bot.handlers.onboarding import (
    answer_learning_question,
    learning_non_text,
)
from app.services.tutor import TutorError


@pytest.mark.asyncio
async def test_learning_question_success():
    message = MagicMock()
    message.text = "Как зарегистрировать заявку?"
    message.answer = AsyncMock()

    tutor = MagicMock()
    tutor.answer = AsyncMock(
        return_value="Заявку нужно зарегистрировать в трекере."
    )

    await answer_learning_question(message, tutor)

    tutor.answer.assert_awaited_once_with(
        "Как зарегистрировать заявку?"
    )
    message.answer.assert_awaited_once_with(
        "Заявку нужно зарегистрировать в трекере."
    )


@pytest.mark.asyncio
async def test_learning_question_tutor_error():
    message = MagicMock()
    message.text = "Как зарегистрировать заявку?"
    message.answer = AsyncMock()

    tutor = MagicMock()
    tutor.answer = AsyncMock(
        side_effect=TutorError("API unavailable")
    )

    await answer_learning_question(message, tutor)

    response = message.answer.call_args.args[0]
    assert "не удалось получить ответ" in response


@pytest.mark.asyncio
async def test_learning_question_too_long():
    message = MagicMock()
    message.text = "А" * 2001
    message.answer = AsyncMock()

    tutor = MagicMock()
    tutor.answer = AsyncMock(
        side_effect=ValueError("Question is too long")
    )

    await answer_learning_question(message, tutor)

    assert "too long" in message.answer.call_args.args[0]


@pytest.mark.asyncio
async def test_learning_non_text():
    message = MagicMock()
    message.answer = AsyncMock()

    await learning_non_text(message)

    message.answer.assert_awaited_once_with(
        "Пожалуйста, отправьте вопрос текстовым сообщением."
    )
