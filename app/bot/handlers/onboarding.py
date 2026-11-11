import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.session import normalize_employee_name
from app.core.training_profile import TrainingProfile
from app.services.training_service import TrainingService
from app.services.tutor import TutorError, TutorService

router = Router()
logger = logging.getLogger(__name__)


class OnboardingStates(StatesGroup):
    waiting_for_name = State()
    learning = State()


DATABASE_ERROR = (
    "Сейчас не удалось обратиться к базе данных.\n"
    "Попробуйте повторить действие позже."
)


def telegram_id(message: Message) -> int | None:
    if message.from_user is None:
        return None
    return message.from_user.id


async def get_active_training(
    session,
    user_id: int,
    profile_id: str,
):
    service = TrainingService(session)
    employee = await service.employees.get_by_telegram_id(user_id)

    if employee is None:
        return None, None

    training = await service.learning.get_active(
        employee.id, profile_id
    )
    return employee, training


async def show_training_status(
    message: Message,
    state: FSMContext,
    status: str,
    employee_name: str,
) -> None:
    if status == "learning":
        await state.set_state(OnboardingStates.learning)
        await message.answer(
            f"Здравствуйте, {employee_name}!\n\n"
            "Ваше обучение продолжается.\n"
            "Можете задавать вопросы по учебному материалу.\n\n"
            "Когда будете готовы проверить знания, отправьте /quiz.\n"
            "Для отмены отправьте /cancel."
        )
        return

    if status == "testing":
        await state.clear()
        await message.answer(
            f"{employee_name}, у вас есть незавершённое тестирование.\n"
            "Для продолжения отправьте /quiz.\n"
            "Если предыдущая попытка не пройдена, используйте /retry."
        )
        return

    await state.clear()
    await message.answer(
        "Текущая учебная сессия пока недоступна "
        "для продолжения."
    )


@router.message(CommandStart())
async def start_onboarding(
    message: Message,
    state: FSMContext,
    training_profile: TrainingProfile,
    session_factory: async_sessionmaker,
) -> None:
    user_id = telegram_id(message)
    if user_id is None:
        return

    try:
        async with session_factory() as session:
            employee, training = await get_active_training(
                session, user_id, training_profile.profile_id
            )
    except SQLAlchemyError:
        logger.exception("Database error in /start")
        await message.answer(DATABASE_ERROR)
        return

    if training is not None and employee is not None:
        await show_training_status(
            message, state, training.status, employee.employee_name
        )
        return

    await state.clear()
    await state.set_state(OnboardingStates.waiting_for_name)
    await message.answer(
        "Здравствуйте! Я AI Onboarding Assistant.\n\n"
        f"Программа: {training_profile.title}\n"
        "Помогу пройти обучение и проверить знания.\n\n"
        "Как вас зовут?"
    )


@router.message(Command("cancel"))
async def cancel_onboarding(
    message: Message,
    state: FSMContext,
    training_profile: TrainingProfile,
    session_factory: async_sessionmaker,
) -> None:
    user_id = telegram_id(message)
    if user_id is None:
        return

    try:
        async with session_factory.begin() as session:
            _, training = await get_active_training(
                session, user_id, training_profile.profile_id
            )

            if training is not None:
                service = TrainingService(session)
                await service.cancel_training(training.id)

    except SQLAlchemyError:
        logger.exception("Database error in /cancel")
        await message.answer(DATABASE_ERROR)
        return
    except ValueError:
        logger.exception("Training cancellation failed")
        await message.answer(
            "Не удалось отменить обучение. "
            "Попробуйте повторить команду."
        )
        return

    await state.clear()

    if training is None:
        await message.answer(
            "Активного обучения нет.\n"
            "Для начала отправьте /start."
        )
    else:
        await message.answer(
            "Учебная сессия отменена.\n"
            "Чтобы начать заново, отправьте /start."
        )


@router.message(OnboardingStates.waiting_for_name, F.text)
async def receive_employee_name(
    message: Message,
    state: FSMContext,
    training_profile: TrainingProfile,
    session_factory: async_sessionmaker,
) -> None:
    user_id = telegram_id(message)
    if user_id is None:
        return

    try:
        name = normalize_employee_name(message.text or "")
    except ValueError as exc:
        await message.answer(str(exc))
        return

    try:
        async with session_factory.begin() as session:
            service = TrainingService(session)
            training = await service.start_or_resume(
                telegram_user_id=user_id,
                employee_name=name,
                username=(
                    message.from_user.username
                    if message.from_user else None
                ),
                profile_id=training_profile.profile_id,
                profile_version=training_profile.version,
            )
            status = training.status

    except SQLAlchemyError:
        logger.exception("Database error while creating training")
        await message.answer(DATABASE_ERROR)
        return

    if status == "learning":
        await state.set_state(OnboardingStates.learning)
        await message.answer(
            f"Приятно познакомиться, {name}!\n\n"
            "Учебная сессия сохранена в PostgreSQL.\n"
            "Можете задавать вопросы по материалу.\n\n"
            "Когда будете готовы проверить знания, отправьте /quiz.\n"
            "Для отмены отправьте /cancel."
        )
    else:
        await show_training_status(message, state, status, name)


@router.message(OnboardingStates.waiting_for_name)
async def receive_invalid_name(message: Message) -> None:
    await message.answer(
        "Пожалуйста, отправьте имя текстовым сообщением."
    )


@router.message(F.text)
async def answer_learning_question(
    message: Message,
    state: FSMContext,
    tutor: TutorService,
    training_profile: TrainingProfile,
    session_factory: async_sessionmaker,
) -> None:
    user_id = telegram_id(message)
    if user_id is None:
        return

    try:
        async with session_factory() as session:
            _, training = await get_active_training(
                session, user_id, training_profile.profile_id
            )
            status = training.status if training else None

    except SQLAlchemyError:
        logger.exception("Database error while loading training")
        await message.answer(DATABASE_ERROR)
        return

    if status == "testing":
        await state.clear()
        await message.answer(
            "У вас есть тестирование. Отправьте /quiz для продолжения."
        )
        return

    if status != "learning":
        await state.clear()
        await message.answer(
            "Чтобы начать обучение, отправьте /start."
        )
        return

    # Восстанавливаем вспомогательное состояние после перезапуска.
    await state.set_state(OnboardingStates.learning)

    if not training_profile.learning.allow_questions:
        await message.answer(
            "Вопросы AI-наставнику отключены "
            "для этой программы обучения."
        )
        return

    try:
        answer = await tutor.answer(message.text or "")
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
async def fallback(
    message: Message,
    state: FSMContext,
    training_profile: TrainingProfile,
    session_factory: async_sessionmaker,
) -> None:
    user_id = telegram_id(message)
    if user_id is None:
        return

    try:
        async with session_factory() as session:
            _, training = await get_active_training(
                session, user_id, training_profile.profile_id
            )
            status = training.status if training else None

    except SQLAlchemyError:
        logger.exception("Database error in fallback")
        await message.answer(DATABASE_ERROR)
        return

    if status == "learning":
        await state.set_state(OnboardingStates.learning)
        await message.answer(
            "Пожалуйста, отправьте вопрос текстовым сообщением."
        )
    elif status == "testing":
        await state.clear()
        await message.answer(
            "У вас есть тестирование. Отправьте /quiz для продолжения."
        )
    else:
        await state.clear()
        await message.answer(
            "Чтобы начать обучение, отправьте /start."
        )
