import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timezone, timedelta

from bot.config import config
from bot.database.db import get_db
from bot.database import queries

router = Router()
logger = logging.getLogger(__name__)

MSK = timezone(timedelta(hours=3))

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
    u = call.from_user
    db = await get_db()
    # Ensure user row exists before setting reminder_time
    await queries.upsert_user(db, u.id, u.username or "", u.first_name or "", u.last_name or "")
    await queries.set_reminder_time(db, u.id, time_str)
    logger.info("Reminder set: user=%s time=%s", u.id, time_str)
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
    now_msk = datetime.now(MSK)
    time_str = now_msk.strftime("%H:%M")

    # Check this user's DB record
    user = await queries.get_user(db, message.from_user.id)
    if user:
        user_exists = "✅ есть в БД"
        reminder_val = user["reminder_time"] or "не установлено"
    else:
        user_exists = "❌ НЕТ в БД — отправь /start"
        reminder_val = "—"

    # Count all users with any reminder set
    all_reminder_users = await db.fetch(
        "SELECT telegram_id, reminder_time FROM users WHERE reminder_time IS NOT NULL"
    )
    users_count = len(all_reminder_users)
    users_list = "\n".join(
        f"  • {r['telegram_id']} → {r['reminder_time']}"
        for r in all_reminder_users
    ) or "  (никого)"

    # Force-send a reminder to this user right now
    test_text = "🔔 ТЕСТ: это проверочное напоминание от планировщика."
    try:
        await message.bot.send_message(message.from_user.id, test_text, parse_mode=None)
        send_status = "✅ Тестовое сообщение отправлено выше"
    except Exception as e:
        send_status = f"❌ Ошибка отправки: {e}"

    await message.answer(
        f"🔍 <b>Диагностика напоминаний</b>\n\n"
        f"🕐 Время МСК: <b>{time_str}</b>\n"
        f"👤 Твой аккаунт: {user_exists}\n"
        f"⏰ Твоё время: <b>{reminder_val}</b>\n\n"
        f"📋 Пользователей с напоминанием: <b>{users_count}</b>\n"
        f"{users_list}\n\n"
        f"{send_status}",
        parse_mode="HTML",
    )
