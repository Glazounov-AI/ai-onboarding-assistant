
import logging
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from openai import AsyncOpenAI
from sqlalchemy import text

from app.bot.handlers.onboarding import router
from app.bot.handlers.quiz import router as quiz_router
from app.core.settings import get_settings
from app.core.training_profile import (
    load_system_prompt,
    load_training_material,
    load_training_profile,
)
from app.database.connection import SessionFactory, engine
from app.services.tutor import TutorService

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


async def run_bot() -> None:
    settings = get_settings()
    settings.validate_runtime()

    logging.basicConfig(
        level=getattr(
            logging, settings.log_level.upper(), logging.INFO
        ),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    profile = load_training_profile(
        PROJECT_ROOT / settings.training_profile
    )
    material = load_training_material(profile, PROJECT_ROOT)
    system_prompt = load_system_prompt(profile, PROJECT_ROOT)

    if settings.openai_api_key is None:
        raise ValueError("OPENAI_API_KEY is required for AI tutor")

    client_kwargs = {
        "api_key": settings.openai_api_key.get_secret_value(),
    }

    if settings.openai_base_url:
        client_kwargs["base_url"] = settings.openai_base_url

    openai_client = AsyncOpenAI(**client_kwargs)
    bot = None
    dispatcher = None

    try:
        # Проверяем БД до начала обработки Telegram-сообщений.
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

        logger.info("PostgreSQL connection verified")

        tutor = TutorService(
            client=openai_client,
            model=settings.openai_model,
            material=material,
            system_prompt=system_prompt,
            temperature=profile.tutor.temperature,
        )

        bot = Bot(token=settings.bot_token.get_secret_value())
        dispatcher = Dispatcher(storage=MemoryStorage())
        dispatcher.include_router(quiz_router)
        dispatcher.include_router(router)

        logger.info(
            "Starting AI Onboarding Assistant: profile=%s, version=%s",
            profile.profile_id,
            profile.version,
        )

        await dispatcher.start_polling(
            bot,
            tutor=tutor,
            training_profile=profile,
            session_factory=SessionFactory,
        )
    finally:
        if dispatcher is not None:
            await dispatcher.storage.close()
        if bot is not None:
            await bot.session.close()
        await openai_client.close()
        await engine.dispose()
