import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from bot.database.db import get_db
from bot.database import queries
from bot.keyboards.reply import main_menu_keyboard
from bot.utils.formatters import format_stats

router = Router()
logger = logging.getLogger(__name__)


@router.message(Command("stats"))
@router.message(F.text == "📊 Статистика")
async def show_stats(message: Message, state: FSMContext) -> None:
    db = await get_db()
    user = message.from_user
    await queries.upsert_user(db, user.id, user.username or "", user.first_name or "", user.last_name or "")
    stats = await queries.get_user_stats(db, user.id)

    if stats["total"] == 0:
        await message.answer(
            "📊 *Статистика пока пуста*\n\n"
            "Начните тренировку, чтобы увидеть свой прогресс\\!",
            parse_mode="MarkdownV2",
            reply_markup=main_menu_keyboard(),
        )
        return

    text = format_stats(stats, user.first_name or "Студент")
    await message.answer(text, parse_mode="MarkdownV2", reply_markup=main_menu_keyboard())
