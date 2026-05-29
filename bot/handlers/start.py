import logging

from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.fsm.context import FSMContext

from bot.config import config
from bot.database.db import get_db
from bot.database import queries
from bot.handlers.admin import is_admin

router = Router()
logger = logging.getLogger(__name__)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    db = await get_db()
    u = message.from_user
    await queries.upsert_user(db, u.id, u.username or "", u.first_name or "", u.last_name or "")

    rows = []
    if config.webapp_url:
        rows.append([InlineKeyboardButton(
            text="🎓 Открыть ФармаКвиз",
            web_app=WebAppInfo(url=config.webapp_url),
        )])
    rows.append([InlineKeyboardButton(
        text="🔔 Напоминания",
        callback_data="open_reminder",
    )])
    if is_admin(u.id):
        rows.append([InlineKeyboardButton(
            text="👑 Статистика студентов",
            callback_data="admin_stats",
        )])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)

    if config.webapp_url:
        text = (
            f"👋 Привет, {u.first_name or 'Студент'}!\n\n"
            "Я помогу тебе подготовиться к экзаменам по фармакологии.\n"
            "Нажми кнопку ниже, чтобы открыть приложение:"
        )
    else:
        text = (
            f"👋 Привет, {u.first_name or 'Студент'}!\n\n"
            "Приложение ФармаКвиз ещё настраивается — скоро будет доступно.\n"
            "Напоминания уже работают 🔔"
        )
    await message.answer(text, reply_markup=kb)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "💊 ФармаКвиз — подготовка к экзаменам по фармакологии\n\n"
        "📖 Тренировка — вопросы с объяснениями\n"
        "📝 Экзамен — с таймером и разбором ошибок\n"
        "📊 Статистика — твой прогресс\n"
        "🔔 /reminder — ежедневное напоминание\n\n"
        "Используй кнопку /start чтобы открыть приложение."
    )
