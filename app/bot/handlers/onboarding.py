from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from app.core.session import normalize_employee_name

router = Router()


class OnboardingStates(StatesGroup):
    waiting_for_name = State()
    learning = State()


@router.message(CommandStart())
async def start_onboarding(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(OnboardingStates.waiting_for_name)

    await message.answer(
        "Здравствуйте! Я AI Onboarding Assistant.\n\n"
        "Помогу пройти обучение и проверить знания.\n\n"
        "Как вас зовут?"
    )


@router.message(Command("cancel"))
async def cancel_onboarding(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Текущая сессия отменена.\n"
        "Чтобы начать заново, отправьте /start."
    )


@router.message(OnboardingStates.waiting_for_name, F.text)
async def receive_employee_name(message: Message, state: FSMContext) -> None:
    try:
        name = normalize_employee_name(message.text or "")
    except ValueError as exc:
        await message.answer(str(exc))
        return

    await state.update_data(
        employee_name=name,
        telegram_user_id=message.from_user.id if message.from_user else None,
    )
    await state.set_state(OnboardingStates.learning)

    await message.answer(
        f"Приятно познакомиться, {name}!\n\n"
        "Учебная сессия создана.\n"
        "Следующий этап — изучение материала.\n\n"
        "Для отмены отправьте /cancel."
    )


@router.message(OnboardingStates.waiting_for_name)
async def receive_invalid_name(message: Message) -> None:
    await message.answer("Пожалуйста, отправьте имя текстовым сообщением.")


@router.message(OnboardingStates.learning)
async def learning_placeholder(message: Message) -> None:
    await message.answer(
        "Сессия обучения активна.\n"
        "Учебный модуль будет подключён на следующем этапе.\n\n"
        "Для перезапуска отправьте /start."
    )


@router.message()
async def fallback(message: Message) -> None:
    await message.answer(
        "Чтобы начать обучение, отправьте /start."
    )