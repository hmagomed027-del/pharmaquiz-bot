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
# Key format: "YYYY-MM-DD HH:MM" — includes date so the same time slot
# is never blocked on the next day.
_last_sent_key: str | None = None


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
        return  # уже отправили в эту минуту сегодня

    db = await get_db()

    # Подстраховка: если планировщик чуть запоздал — проверяем предыдущую минуту
    prev_msk = now_msk - timedelta(minutes=1)
    prev_time = prev_msk.strftime("%H:%M")
    prev_key = prev_msk.strftime("%Y-%m-%d %H:%M")

    users = await queries.get_users_for_reminder(db, time_str)
    if not users and prev_key != _last_sent_key:
        users = await queries.get_users_for_reminder(db, prev_time)
        if users:
            current_key = prev_key
            time_str = prev_time

    if not users:
        return

    logger.info("Sending reminders at %s MSK to %d users", time_str, len(users))
    text = _next_message()
    sent = failed = blocked = 0

    for user in users:
        try:
            await bot.send_message(user["telegram_id"], text, parse_mode=None)
            sent += 1
        except TelegramForbiddenError:
            blocked += 1
        except TelegramBadRequest as e:
            failed += 1
            logger.error("TelegramBadRequest for user %s: %s | text=%r", user["telegram_id"], e, text)
        except Exception as e:
            failed += 1
            logger.warning("Failed to send reminder to %s: %s", user["telegram_id"], e)

    logger.info("Reminders done: sent=%d blocked=%d failed=%d", sent, blocked, failed)
    _last_sent_key = current_key


async def reminder_scheduler(bot: Bot) -> None:
    logger.info("Reminder scheduler started")
    while True:
        try:
            await _send_reminders(bot)
        except Exception as e:
            logger.error("Scheduler error: %s", e)
        await asyncio.sleep(60)
