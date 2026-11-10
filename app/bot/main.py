import logging
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from openai import AsyncOpenAI

from app.bot.handlers.onboarding import router
from app.core.settings import get_settings
from app.core.training_profile import (
    load_system_prompt,
    load_training_material,
    load_training_profile,
)
from app.services.tutor import TutorService

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


async def run_bot() -> None:
    settings = get_settings()
    settings.validate_runtime()

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    profile = load_training_profile(
        PROJECT_ROOT / settings.training_profile
    )
    material = load_training_material(profile, PROJECT_ROOT)
    system_prompt = load_system_prompt(profile, PROJECT_ROOT)

    if settings.openai_api_key is None:
        raise ValueError(
            "OPENAI_API_KEY is required for AI tutor"
        )

    client_kwargs = {
        "api_key": settings.openai_api_key.get_secret_value(),
    }

    if settings.openai_base_url:
        client_kwargs["base_url"] = settings.openai_base_url

    openai_client = AsyncOpenAI(**client_kwargs)

    tutor = TutorService(
        client=openai_client,
        model=settings.openai_model,
        material=material,
        system_prompt=system_prompt,
        temperature=profile.tutor.temperature,
    )

    bot = None

    try:
        bot = Bot(token=settings.bot_token.get_secret_value())
        dispatcher = Dispatcher(storage=MemoryStorage())
        dispatcher.include_router(router)

        logger.info(
            "Starting AI Onboarding Assistant: profile=%s",
            profile.profile_id,
        )

        await dispatcher.start_polling(
            bot,
            tutor=tutor,
            training_title=profile.title,
        )
    finally:
        if bot is not None:
            await bot.session.close()
        await openai_client.close()