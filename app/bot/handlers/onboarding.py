import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from app.core.session import normalize_employee_name
from app.services.tutor import TutorError, TutorService

router = Router()

logger = logging.getLogger(__name__)

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


@router.message(OnboardingStates.learning, F.text)
async def answer_learning_question(
    message: Message,
    tutor: TutorService,
) -> None:
    question = message.text or ""

    try:
        answer = await tutor.answer(question)
    except ValueError as exc:
        await message.answer(str(exc))
        return
    except TutorError:
        logger.exception("AI tutor request failed")
        await message.answer(
            "Сейчас не удалось получить ответ AI-наставника.\n"
            "Попробуйте повторить вопрос позже."
        )
        return

    await message.answer(answer)


@router.message(OnboardingStates.learning)
async def learning_non_text(message: Message) -> None:
    await message.answer(
        "Пожалуйста, отправьте вопрос текстовым сообщением."
    )


@router.message()
async def fallback(message: Message, state: FSMContext) -> None:
    current_state = await state.get_state()

    logger.warning(
        "Fallback triggered: user_id=%s, state=%s, text=%r",
        message.from_user.id if message.from_user else None,
        current_state,
        message.text,
    )

    await message.answer(
        "Чтобы начать обучение, отправьте /start."
    )
