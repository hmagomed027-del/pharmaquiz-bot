import logging

from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo,
    ReplyKeyboardMarkup, KeyboardButton,
)
from aiogram.fsm.context import FSMContext

from bot.config import config
from bot.database.db import get_db
from bot.database import queries

router = Router()
logger = logging.getLogger(__name__)


def _is_admin(user_id: int) -> bool:
    return user_id in config.admin_ids


def _main_reply_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="🎓 ФармаКвиз"), KeyboardButton(text="🔔 Напоминания")],
        [KeyboardButton(text="💊 Помощь")],
    ]
    if is_admin:
        rows[1].append(KeyboardButton(text="📊 Статистика"))
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def _webapp_inline_kb() -> InlineKeyboardMarkup | None:
    if not config.webapp_url:
        return None
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="🎓 Открыть приложение",
            web_app=WebAppInfo(url=config.webapp_url),
        )
    ]])


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    db = await get_db()
    u = message.from_user
    await queries.upsert_user(db, u.id, u.username or "", u.first_name or "", u.last_name or "")

    name = u.first_name or "Студент"
    reply_kb = _main_reply_keyboard(is_admin=_is_admin(u.id))

    await message.answer(
        f"👋 Привет, {name}!\n\n"
        "💊 ФармаКвиз — твой тренажёр по фармакологии.\n"
        "Тренируйся по темам, сдавай экзамены и следи за прогрессом.",
        reply_markup=reply_kb,
        parse_mode=None,
    )

    # Если есть webapp — отдельным сообщением кнопка открытия
    inline_kb = _webapp_inline_kb()
    if inline_kb:
        await message.answer(
            "Нажми чтобы открыть приложение:",
            reply_markup=inline_kb,
            parse_mode=None,
        )


# ── Обработчики кнопок reply-клавиатуры ──────────────────────────────────────

@router.message(F.text == "🎓 ФармаКвиз")
async def btn_app(message: Message) -> None:
    inline_kb = _webapp_inline_kb()
    if inline_kb:
        await message.answer("Нажми чтобы открыть приложение:", reply_markup=inline_kb, parse_mode=None)
    else:
        await message.answer("Приложение скоро будет доступно.", parse_mode=None)


@router.message(F.text == "🔔 Напоминания")
async def btn_reminder(message: Message) -> None:
    from bot.handlers.reminder import _show_reminder_menu
    await _show_reminder_menu(message.from_user.id, message.answer)


@router.message(F.text == "💊 Помощь")
async def btn_help(message: Message) -> None:
    await cmd_help(message)


@router.message(F.text == "📊 Статистика")
async def btn_stats(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return
    from bot.handlers.admin import _adminstats_body
    await _adminstats_body(message)


# ── Команды ───────────────────────────────────────────────────────────────────

@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "💊 ФармаКвиз — подготовка к экзаменам по фармакологии\n\n"
        "📖 Тренировка — вопросы с объяснениями\n"
        "📝 Экзамен — с таймером и разбором ошибок\n"
        "📊 Статистика — твой прогресс\n"
        "🔔 Напоминания — ежедневное напоминание\n\n"
        "Используй кнопки меню внизу для навигации.",
        parse_mode=None,
    )
