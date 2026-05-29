import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

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


async def _show_reminder_menu(user_id: int, first_name: str, answer_fn) -> None:
    db = await get_db()
    user = await queries.get_user(db, user_id)
    current = user["reminder_time"] if user else None
    status = f"Сейчас: *{current}* по МСК" if current else "Сейчас: *отключено*"
    await answer_fn(
        f"🔔 *Напоминания о занятиях*\n\n"
        f"{status}\n\n"
        "Выбери время — бот напомнит, если ты не занимался больше дня\\.",
        reply_markup=_reminder_keyboard(current),
        parse_mode="MarkdownV2",
    )


@router.callback_query(F.data == "open_reminder")
async def cb_open_reminder(call: CallbackQuery) -> None:
    await _show_reminder_menu(
        call.from_user.id,
        call.from_user.first_name,
        call.message.answer,
    )
    await call.answer()


@router.message(Command("reminder"))
async def cmd_reminder(message: Message) -> None:
    await _show_reminder_menu(message.from_user.id, message.from_user.first_name, message.answer)


@router.callback_query(F.data.startswith("reminder_set:"))
async def cb_reminder_set(call: CallbackQuery) -> None:
    time_str = call.data.split(":")[1]
    db = await get_db()
    await queries.set_reminder_time(db, call.from_user.id, time_str)
    await call.message.edit_text(
        f"✅ Напоминание установлено на *{time_str}* \\(МСК\\)\\.\n\n"
        "Если не будешь заниматься весь день — пришлю напоминание в это время\\.",
        reply_markup=_reminder_keyboard(time_str),
        parse_mode="MarkdownV2",
    )
    await call.answer()


@router.callback_query(F.data == "reminder_off")
async def cb_reminder_off(call: CallbackQuery) -> None:
    db = await get_db()
    await queries.set_reminder_time(db, call.from_user.id, None)
    await call.message.edit_text(
        "🔕 Напоминания отключены\\.",
        reply_markup=_reminder_keyboard(None),
        parse_mode="MarkdownV2",
    )
    await call.answer()
