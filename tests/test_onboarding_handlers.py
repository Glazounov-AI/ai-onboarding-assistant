from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

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
    msg.from_user.username = "ivan"
    msg.text = "Иван Петров"
    return msg


@pytest.fixture
def state():
    ctx = MagicMock()
    ctx.clear = AsyncMock()
    ctx.set_state = AsyncMock()
    ctx.update_data = AsyncMock()
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

    factory = MagicMock(return_value=session)

    transaction = MagicMock()
    transaction.__aenter__ = AsyncMock(return_value=session)
    transaction.__aexit__ = AsyncMock(return_value=None)

    factory.begin.return_value = transaction
    return factory


@pytest.mark.asyncio
async def test_start_onboarding(
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
    state.set_state.assert_awaited_once_with(
        OnboardingStates.waiting_for_name
    )
    message.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_start_restores_active_training(
    message, state, profile, session_factory
):
    employee = SimpleNamespace(employee_name="Иван Петров")
    training = SimpleNamespace(id=10, status="learning")

    with patch(
        "app.bot.handlers.onboarding.get_active_training",
        new_callable=AsyncMock,
        return_value=(employee, training),
    ):
        await start_onboarding(
            message, state, profile, session_factory
        )

    state.set_state.assert_awaited_once_with(
        OnboardingStates.learning
    )

    response = message.answer.call_args.args[0]
    assert "продолжается" in response


@pytest.mark.asyncio
async def test_receive_employee_name(
    message, state, profile, session_factory
):
    training = SimpleNamespace(id=10, status="learning")

    with patch(
        "app.bot.handlers.onboarding.TrainingService"
    ) as service_class:
        service = service_class.return_value
        service.start_or_resume = AsyncMock(
            return_value=training
        )

        await receive_employee_name(
            message, state, profile, session_factory
        )

        service.start_or_resume.assert_awaited_once_with(
            telegram_user_id=12345,
            employee_name="Иван Петров",
            username="ivan",
            profile_id="demo",
            profile_version=1,
        )

    state.set_state.assert_awaited_once_with(
        OnboardingStates.learning
    )
    message.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_cancel_onboarding(
    message, state, profile, session_factory
):
    employee = SimpleNamespace(id=1)
    training = SimpleNamespace(id=10, status="learning")

    with (
        patch(
            "app.bot.handlers.onboarding.get_active_training",
            new_callable=AsyncMock,
            return_value=(employee, training),
        ),
        patch(
            "app.bot.handlers.onboarding.TrainingService"
        ) as service_class,
    ):
        service = service_class.return_value
        service.cancel_training = AsyncMock()

        await cancel_onboarding(
            message, state, profile, session_factory
        )

        service.cancel_training.assert_awaited_once_with(10)

    state.clear.assert_awaited_once()
    message.answer.assert_awaited_once()

    response = message.answer.call_args.args[0]
    assert "отменена" in response


@pytest.mark.asyncio
async def test_cancel_without_active_training(
    message, state, profile, session_factory
):
    with patch(
        "app.bot.handlers.onboarding.get_active_training",
        new_callable=AsyncMock,
        return_value=(None, None),
    ):
        await cancel_onboarding(
            message, state, profile, session_factory
        )

    state.clear.assert_awaited_once()

    response = message.answer.call_args.args[0]
    assert "Активного обучения нет" in response
