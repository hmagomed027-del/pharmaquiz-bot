"""
Combined entry point: runs FastAPI (Mini App + API) and Telegram bot together.
"""
import asyncio
import logging
import os
import sys

import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import config
from bot.database.db import init_db, close_db, get_db
from bot.services.question_loader import load_all_questions
from bot.services.wikipedia_service import close_session
from bot.services.scheduler import reminder_scheduler
from bot.middlewares.throttling import ThrottlingMiddleware
from bot.handlers import start, training, exam, stats, admin, reminder
from api.main import app as fastapi_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


async def run_bot() -> None:
    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2),
    )

    # Сбрасываем вебхук и закрываем старые polling-сессии перед стартом
    await bot.delete_webhook(drop_pending_updates=True)

    dp = Dispatcher(storage=MemoryStorage())
    dp.message.middleware(ThrottlingMiddleware(rate=config.throttle_rate))

    dp.include_router(admin.router)
    dp.include_router(reminder.router)
    dp.include_router(training.router)
    dp.include_router(exam.router)
    dp.include_router(stats.router)
    dp.include_router(start.router)

    me = await bot.get_me()
    logger.info("Telegram bot started: @%s", me.username)

    asyncio.create_task(reminder_scheduler(bot))

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await close_session()
        await close_db()
        logger.info("Bot stopped")


async def main() -> None:
    port = int(os.getenv("PORT", "8000"))
    server = uvicorn.Server(
        uvicorn.Config(fastapi_app, host="0.0.0.0", port=port, log_level="info")
    )

    logger.info("Starting FastAPI on port %d ...", port)
    await asyncio.gather(server.serve(), run_bot())


if __name__ == "__main__":
    asyncio.run(main())
