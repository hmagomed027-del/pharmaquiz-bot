"""
Entry point: FastAPI (Mini App + API) + Telegram bot via webhook.
Webhook mode eliminates TelegramConflictError during Render zero-downtime deploys.
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
from aiogram.types import Update
from fastapi import Request

from bot.config import config
from bot.middlewares.throttling import ThrottlingMiddleware
from bot.services.scheduler import reminder_scheduler
from bot.handlers import start, training, exam, stats, admin, reminder
from api.main import app as fastapi_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

bot = Bot(
    token=config.bot_token,
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2),
)
dp = Dispatcher(storage=MemoryStorage())
dp.message.middleware(ThrottlingMiddleware(rate=config.throttle_rate))
dp.include_router(admin.router)
dp.include_router(reminder.router)
dp.include_router(training.router)
dp.include_router(exam.router)
dp.include_router(stats.router)
dp.include_router(start.router)


@fastapi_app.post("/webhook", include_in_schema=False)
async def telegram_webhook(request: Request):
    update = Update.model_validate(await request.json(), context={"bot": bot})
    await dp.feed_update(bot, update)
    return {"ok": True}


async def main() -> None:
    port = int(os.getenv("PORT", "8000"))
    server = uvicorn.Server(
        uvicorn.Config(fastapi_app, host="0.0.0.0", port=port, log_level="info")
    )

    await server.startup()
    logger.info("FastAPI running on port %d", port)

    webhook_url = f"{config.webapp_url}/webhook"
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(webhook_url, drop_pending_updates=True)
    logger.info("Webhook set: %s", webhook_url)

    asyncio.create_task(reminder_scheduler(bot))

    try:
        await server.main_loop()
    finally:
        await server.shutdown()
        await bot.delete_webhook()
        await bot.session.close()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
