from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.bot.handlers.onboarding import (
    answer_learning_question,
    start_onboarding,
)


@pytest.fixture
def message():
    msg = MagicMock()
    msg.from_user.id = 900001
    msg.from_user.username = "test_user"
    msg.text = "Что нужно изучить?"
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
        profile_id="test-profile",
        version=1,
        title="Тестовая программа",
        learning=SimpleNamespace(allow_questions=True),
    )


@pytest.fixture
def session_factory():
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)

    factory = MagicMock(return_value=session)
    return factory


@pytest.mark.asyncio
async def test_start_requests_name_without_active_training(
    message, state, profile, session_factory
):
    with patch(
        "app.bot.handlers.onboarding.get_active_training",
        new_callable=AsyncMock,
        return_value=(None, None),
    ):
        await start_onboarding(
            message, state, profile, session_factory
        )

    state.clear.assert_awaited_once()
    state.set_state.assert_awaited_once()
    assert "Как вас зовут?" in message.answer.await_args.args[0]


@pytest.mark.asyncio
async def test_start_restores_existing_training(
    message, state, profile, session_factory
):
    employee = SimpleNamespace(employee_name="Иван")
    training = SimpleNamespace(status="learning", id=10)

    with patch(
        "app.bot.handlers.onboarding.get_active_training",
        new_callable=AsyncMock,
        return_value=(employee, training),
    ):
        await start_onboarding(
            message, state, profile, session_factory
        )

    state.set_state.assert_awaited_once()
    assert "продолжается" in message.answer.await_args.args[0]


@pytest.mark.asyncio
async def test_tutor_works_without_fsm_state(
    message, state, profile, session_factory
):
    employee = SimpleNamespace(employee_name="Иван")
    training = SimpleNamespace(status="learning", id=10)
    tutor = MagicMock()
    tutor.answer = AsyncMock(return_value="Ответ наставника")

    with patch(
        "app.bot.handlers.onboarding.get_active_training",
        new_callable=AsyncMock,
        return_value=(employee, training),
    ):
        await answer_learning_question(
            message,
            state,
            tutor,
            profile,
            session_factory,
        )

    tutor.answer.assert_awaited_once_with(
        "Что нужно изучить?"
    )
    message.answer.assert_awaited_once_with(
        "Ответ наставника"
    )
    state.set_state.assert_awaited_once()
