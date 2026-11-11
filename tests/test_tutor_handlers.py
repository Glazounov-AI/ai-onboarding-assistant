
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.bot.handlers.onboarding import (
    OnboardingStates,
    answer_learning_question,
    learning_non_text,
)
from app.services.tutor import TutorError


@pytest.fixture
def message():
    msg = MagicMock()
    msg.from_user.id = 12345
    msg.text = "Как зарегистрировать заявку?"
    msg.answer = AsyncMock()
    return msg


@pytest.fixture
def state():
    ctx = MagicMock()
    ctx.clear = AsyncMock()
    ctx.set_state = AsyncMock()
    return ctx


@pytest.fixture
def profile():
    return SimpleNamespace(
        profile_id="demo",
        version=1,
        title="Тестовая программа",
        learning=SimpleNamespace(allow_questions=True),
    )


@pytest.fixture
def session_factory():
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)

    return MagicMock(return_value=session)


@pytest.fixture
def active_training():
    employee = SimpleNamespace(
        id=1,
        employee_name="Иван Петров",
    )
    training = SimpleNamespace(
        id=10,
        status="learning",
    )
    return employee, training


@pytest.mark.asyncio
async def test_learning_question_success(
    message,
    state,
    profile,
    session_factory,
    active_training,
):
    tutor = MagicMock()
    tutor.answer = AsyncMock(
        return_value="Заявку нужно зарегистрировать в трекере."
    )

    with patch(
        "app.bot.handlers.onboarding.get_active_training",
        new_callable=AsyncMock,
        return_value=active_training,
    ):
        await answer_learning_question(
            message,
            state,
            tutor,
            profile,
            session_factory,
        )

    tutor.answer.assert_awaited_once_with(
        "Как зарегистрировать заявку?"
    )
    message.answer.assert_awaited_once_with(
        "Заявку нужно зарегистрировать в трекере."
    )
    state.set_state.assert_awaited_once_with(
        OnboardingStates.learning
    )


@pytest.mark.asyncio
async def test_learning_question_tutor_error(
    message,
    state,
    profile,
    session_factory,
    active_training,
):
    tutor = MagicMock()
    tutor.answer = AsyncMock(
        side_effect=TutorError("API unavailable")
    )

    with patch(
        "app.bot.handlers.onboarding.get_active_training",
        new_callable=AsyncMock,
        return_value=active_training,
    ):
        await answer_learning_question(
            message,
            state,
            tutor,
            profile,
            session_factory,
        )

    response = message.answer.call_args.args[0]
    assert "не удалось получить ответ" in response


@pytest.mark.asyncio
async def test_learning_question_too_long(
    message,
    state,
    profile,
    session_factory,
    active_training,
):
    message.text = "А" * 2001

    tutor = MagicMock()
    tutor.answer = AsyncMock(
        side_effect=ValueError("Question is too long")
    )

    with patch(
        "app.bot.handlers.onboarding.get_active_training",
        new_callable=AsyncMock,
        return_value=active_training,
    ):
        await answer_learning_question(
            message,
            state,
            tutor,
            profile,
            session_factory,
        )

    assert "too long" in message.answer.call_args.args[0]


@pytest.mark.asyncio
async def test_learning_question_without_active_training(
    message,
    state,
    profile,
    session_factory,
):
    tutor = MagicMock()
    tutor.answer = AsyncMock()

    with patch(
        "app.bot.handlers.onboarding.get_active_training",
        new_callable=AsyncMock,
        return_value=(None, None),
    ):
        await answer_learning_question(
            message,
            state,
            tutor,
            profile,
            session_factory,
        )

    tutor.answer.assert_not_awaited()
    state.clear.assert_awaited_once()

    response = message.answer.call_args.args[0]
    assert "/start" in response


@pytest.mark.asyncio
async def test_learning_question_disabled(
    message,
    state,
    profile,
    session_factory,
    active_training,
):
    profile.learning.allow_questions = False

    tutor = MagicMock()
    tutor.answer = AsyncMock()

    with patch(
        "app.bot.handlers.onboarding.get_active_training",
        new_callable=AsyncMock,
        return_value=active_training,
    ):
        await answer_learning_question(
            message,
            state,
            tutor,
            profile,
            session_factory,
        )

    tutor.answer.assert_not_awaited()

    response = message.answer.call_args.args[0]
    assert "отключены" in response


@pytest.mark.asyncio
async def test_learning_non_text():
    message = MagicMock()
    message.answer = AsyncMock()

    await learning_non_text(message)

    message.answer.assert_awaited_once_with(
        "Пожалуйста, отправьте вопрос текстовым сообщением."
    )
