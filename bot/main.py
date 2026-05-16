import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import config
from bot.database.db import init_db, close_db, get_db
from bot.services.question_loader import load_all_questions
from bot.services.wikipedia_service import close_session
from bot.middlewares.throttling import ThrottlingMiddleware

from bot.handlers import start, training, exam, stats, admin

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


async def main() -> None:
    # Устанавливаем рабочую директорию в папку проекта
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(project_dir)
    logger.info("Working directory: %s", project_dir)

    # Создаём нужные папки
    os.makedirs(config.images_dir, exist_ok=True)

    # Инициализируем базу данных
    logger.info("Initialising database...")
    await init_db(config.database_path)

    # Загружаем вопросы из JSON-файлов
    db = await get_db()
    logger.info("Loading questions from data/questions/...")
    count = await load_all_questions(db)
    logger.info("Questions loaded: %d new", count)

    # Проверяем что вопросы есть
    from bot.database import queries
    topic_counts = await queries.count_questions_by_topic(db)
    if topic_counts:
        logger.info("Topics in DB: %s", dict(topic_counts))
    else:
        logger.warning("No questions in database! Check data/questions/ folder.")

    # Создаём бота и диспетчер
    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2),
    )
    dp = Dispatcher(storage=MemoryStorage())

    dp.message.middleware(ThrottlingMiddleware(rate=config.throttle_rate))

    dp.include_router(admin.router)
    dp.include_router(training.router)
    dp.include_router(exam.router)
    dp.include_router(stats.router)
    dp.include_router(start.router)

    me = await bot.get_me()
    logger.info("Bot started: @%s", me.username)

    try:
        await dp.start_polling(bot)
    finally:
        await close_session()
        await close_db()
        logger.info("Bot stopped")


if __name__ == "__main__":
    asyncio.run(main())
