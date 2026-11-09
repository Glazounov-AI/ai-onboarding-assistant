import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.bot.handlers.onboarding import router
from app.core.settings import get_settings

# Set up logging
logger = logging.getLogger(__name__)

async def run_bot() -> None:
    settings = get_settings()
    settings.validate_runtime()

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    bot = Bot(token=settings.bot_token.get_secret_value())
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.include_router(router)

    try:
        logger.info("Starting AI Onboarding Assistant")
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()