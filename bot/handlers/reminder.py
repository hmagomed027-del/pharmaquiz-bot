import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from bot.config import config
from bot.database.db import get_db
from bot.database import queries

router = Router()
logger = logging.getLogger(__name__)

TIMES = ["07:00", "08:00", "09:00", "10:00", "12:00", "14:00",
         "16:00", "18:00", "19:00", "20:00", "21:00", "22:00"]


def _reminder_keyboard(current: str | None) -> InlineKeyboardMarkup:
    buttons = []
    row = []
    for t in TIMES:
        label = f"✅ {t}" if t == current else t
        row.append(InlineKeyboardButton(text=label, callback_data=f"reminder_set:{t}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    off_label = "🔕 Отключено" if current is None else "🔕 Отключить"
    buttons.append([InlineKeyboardButton(text=off_label, callback_data="reminder_off")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def _show_reminder_menu(user_id: int, answer_fn) -> None:
    db = await get_db()
    user = await queries.get_user(db, user_id)
    current = user["reminder_time"] if user else None
    status = f"Сейчас: <b>{current}</b> по МСК" if current else "Сейчас: <b>отключено</b>"
    await answer_fn(
        f"🔔 <b>Напоминания о занятиях</b>\n\n"
        f"{status}\n\n"
        "Выбери время — бот будет напоминать каждый день в это время.",
        reply_markup=_reminder_keyboard(current),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "open_reminder")
async def cb_open_reminder(call: CallbackQuery) -> None:
    await call.answer()
    await _show_reminder_menu(call.from_user.id, call.message.answer)


@router.message(Command("reminder"))
@router.message(F.text == "🔔 Напоминания")
async def cmd_reminder(message: Message) -> None:
    await _show_reminder_menu(message.from_user.id, message.answer)


@router.callback_query(F.data.startswith("reminder_set:"))
async def cb_reminder_set(call: CallbackQuery) -> None:
    await call.answer()
    time_str = call.data[len("reminder_set:"):]
    db = await get_db()
    await queries.set_reminder_time(db, call.from_user.id, time_str)
    await call.message.edit_text(
        f"✅ Напоминание установлено на <b>{time_str}</b> (МСК).\n\n"
        "Каждый день в это время буду напоминать о занятиях.",
        reply_markup=_reminder_keyboard(time_str),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "reminder_off")
async def cb_reminder_off(call: CallbackQuery) -> None:
    await call.answer()
    db = await get_db()
    await queries.set_reminder_time(db, call.from_user.id, None)
    await call.message.edit_text(
        "🔕 Напоминания отключены.",
        reply_markup=_reminder_keyboard(None),
        parse_mode="HTML",
    )


@router.message(Command("testreminder"))
async def cmd_test_reminder(message: Message) -> None:
    if message.from_user.id not in config.admin_ids:
        return
    db = await get_db()
    user = await queries.get_user(db, message.from_user.id)
    current = user["reminder_time"] if user else None
    text = (
        "📚 Привет! Ты давно не занимался фармакологией. "
        "Самое время освежить знания!"
    )
    await message.answer(
        f"🔔 <b>Тест напоминания</b>\n"
        f"Твоё время: <b>{current or 'не установлено'}</b>\n\n"
        f"Вот так выглядит напоминание:\n\n{text}",
        parse_mode="HTML",
    )
