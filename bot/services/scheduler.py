import asyncio
import logging
from datetime import datetime, timezone, timedelta

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from bot.database.db import get_db
from bot.database import queries

logger = logging.getLogger(__name__)

MSK = timezone(timedelta(hours=3))

MESSAGES = [
    "📚 Привет! Ты давно не занимался фармакологией. Самое время освежить знания!",
    "💊 Не забывай про подготовку! Зайди порешай пару вопросов — это займёт всего 5 минут.",
    "🎓 Регулярные занятия — ключ к успеху на экзамене. Сегодня ещё не занимался!",
    "⏰ Напоминаю: ежедневная практика по фармакологии ждёт тебя!",
    "🧠 Чем чаще повторяешь — тем лучше запоминаешь. Зайди позанимайся!",
]

_msg_index = 0
_last_sent_key: str | None = None  # "YYYY-MM-DD HH:MM"


def _next_message() -> str:
    global _msg_index
    msg = MESSAGES[_msg_index % len(MESSAGES)]
    _msg_index += 1
    return msg


async def _send_reminders(bot: Bot) -> None:
    global _last_sent_key

    now_msk = datetime.now(MSK)
    time_str = now_msk.strftime("%H:%M")
    current_key = now_msk.strftime("%Y-%m-%d %H:%M")

    if current_key == _last_sent_key:
        return

    db = await get_db()

    # Also check previous minute in case scheduler fired a few seconds late
    prev_msk = now_msk - timedelta(minutes=1)
    prev_time = prev_msk.strftime("%H:%M")
    prev_key  = prev_msk.strftime("%Y-%m-%d %H:%M")

    users = await queries.get_users_for_reminder(db, time_str)
    if not users and prev_key != _last_sent_key:
        users = await queries.get_users_for_reminder(db, prev_time)
        if users:
            current_key = prev_key
            time_str = prev_time

    # Log every minute so Render logs confirm scheduler is alive and show what it found
    logger.info("Scheduler tick MSK=%s — matched %d user(s) for reminder", time_str, len(users))

    if not users:
        _last_sent_key = current_key   # mark minute as processed even with 0 users
        return

    text = _next_message()
    sent = failed = blocked = 0

    for user in users:
        try:
            await bot.send_message(user["telegram_id"], text, parse_mode=None)
            sent += 1
            logger.info("  → sent to uid=%s", user["telegram_id"])
        except TelegramForbiddenError:
            blocked += 1
            logger.warning("  → uid=%s blocked the bot", user["telegram_id"])
        except TelegramBadRequest as e:
            failed += 1
            logger.error("  → TelegramBadRequest uid=%s: %s", user["telegram_id"], e)
        except Exception as e:
            failed += 1
            logger.error("  → error uid=%s: %s", user["telegram_id"], e)

    logger.info("Reminders done — sent=%d blocked=%d failed=%d", sent, blocked, failed)
    _last_sent_key = current_key


async def reminder_scheduler(bot: Bot) -> None:
    logger.info("Reminder scheduler started")
    # Log initial DB state so it's visible in Render logs on startup
    try:
        db = await get_db()
        rows = await db.fetch(
            "SELECT telegram_id, reminder_time FROM users WHERE reminder_time IS NOT NULL"
        )
        if rows:
            logger.info("Users with reminder set (%d): %s",
                        len(rows),
                        [(r["telegram_id"], r["reminder_time"]) for r in rows])
        else:
            logger.warning("No users have reminder_time set — reminders will not fire. "
                           "Users must set a reminder via /reminder after DB migration.")
    except Exception as e:
        logger.error("Startup reminder check failed: %s", e)

    while True:
        try:
            await _send_reminders(bot)
        except Exception as e:
            logger.error("Scheduler error: %s", e, exc_info=True)
        await asyncio.sleep(60)
