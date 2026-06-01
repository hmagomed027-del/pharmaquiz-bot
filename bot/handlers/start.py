import logging

from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from bot.config import config
from bot.database.db import get_db
from bot.database import queries
from bot.keyboards.reply import get_menu_keyboard

router = Router()
logger = logging.getLogger(__name__)


def _is_admin(user_id: int) -> bool:
    return user_id in config.admin_ids


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    db = await get_db()
    u = message.from_user
    await queries.upsert_user(db, u.id, u.username or "", u.first_name or "", u.last_name or "")

    name = u.first_name or "Студент"
    reply_kb = get_menu_keyboard(u.id)

    await message.answer(
        f"👋 Привет, {name}!\n\n"
        "💊 ФармаКвиз — твой тренажёр по фармакологии.\n"
        "Тренируйся по темам, сдавай экзамены и следи за прогрессом.\n\n"
        "Используй кнопки меню ниже 👇",
        reply_markup=reply_kb,
        parse_mode=None,
    )


@router.message(Command("help"))
@router.message(F.text == "ℹ️ Помощь")
async def cmd_help(message: Message) -> None:
    await message.answer(
        "💊 ФармаКвиз — подготовка к экзаменам по фармакологии\n\n"
        "📚 Тренировка — вопросы с объяснениями от AI\n"
        "📝 Экзамен — с таймером и разбором ошибок\n"
        "📊 Статистика — твой прогресс по темам\n"
        "🔔 Напоминания — ежедневный сигнал о занятиях\n\n"
        "Используй кнопки меню внизу для навигации.",
        reply_markup=get_menu_keyboard(message.from_user.id),
        parse_mode=None,
    )
