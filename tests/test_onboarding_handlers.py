from unittest.mock import AsyncMock, MagicMock

import pytest

from app.bot.handlers.onboarding import (
    OnboardingStates,
    cancel_onboarding,
    receive_employee_name,
    start_onboarding,
)


@pytest.fixture
def message():
    msg = MagicMock()
    msg.answer = AsyncMock()
    msg.from_user.id = 12345
    msg.text = "Иван Петров"
    return msg


@pytest.fixture
def state():
    ctx = MagicMock()
    ctx.clear = AsyncMock()
    ctx.set_state = AsyncMock()
    ctx.update_data = AsyncMock()
    return ctx


@pytest.mark.asyncio
async def test_start_onboarding(message, state):
    await start_onboarding(message, state)

    state.clear.assert_awaited_once()
    state.set_state.assert_awaited_once_with(
        OnboardingStates.waiting_for_name
    )
    message.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_receive_employee_name(message, state):
    await receive_employee_name(message, state)

    state.update_data.assert_awaited_once_with(
        employee_name="Иван Петров",
        telegram_user_id=12345,
    )
    state.set_state.assert_awaited_once_with(
        OnboardingStates.learning
    )


@pytest.mark.asyncio
async def test_cancel_onboarding(message, state):
    await cancel_onboarding(message, state)

    state.clear.assert_awaited_once()
    message.answer.assert_awaited_once()