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
from bot.handlers.start import router as start_router
from bot.middlewares.throttling import ThrottlingMiddleware
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
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.message.middleware(ThrottlingMiddleware(rate=config.throttle_rate))
    dp.include_router(start_router)

    me = await bot.get_me()
    logger.info("Telegram bot started: @%s", me.username)

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


async def main() -> None:
    port = int(os.getenv("PORT", "8000"))
    server = uvicorn.Server(
        uvicorn.Config(fastapi_app, host="0.0.0.0", port=port, log_level="info")
    )

    logger.info("Starting FastAPI on port %d ...", port)
    await asyncio.gather(server.serve(), run_bot())


if __name__ == "__main__":
    asyncio.run(main())
