import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from bot.config import config
from bot.database.db import get_db
from bot.database import queries
from bot.services.question_loader import load_all_questions
from bot.states.states import AdminStates
from bot.utils.formatters import escape_md

router = Router()
logger = logging.getLogger(__name__)


def is_admin(user_id: int) -> bool:
    return user_id in config.admin_ids


@router.message(Command("reload"))
async def cmd_reload(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return
    db = await get_db()
    count = await load_all_questions(db)
    topic_counts = await queries.count_questions_by_topic(db)
    lines = [f"🔄 *Загрузка завершена*", f"Новых вопросов: *{count}*", "", "*Всего по темам:*"]
    for topic, cnt in sorted(topic_counts.items()):
        lines.append(f"• {escape_md(topic)}: {cnt}")
    await message.answer("\n".join(lines), parse_mode="MarkdownV2")


@router.message(Command("dbstats"))
async def cmd_dbstats(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return
    db = await get_db()
    topic_counts = await queries.count_questions_by_topic(db)
    users = await queries.get_all_users(db)
    lines = [f"📊 *Статистика базы данных*", "", f"Пользователей: *{len(users)}*", "", "*Вопросов по темам:*"]
    for topic, cnt in sorted(topic_counts.items()):
        lines.append(f"• {escape_md(topic)}: {cnt}")
    await message.answer("\n".join(lines), parse_mode="MarkdownV2")


@router.message(Command("broadcast"))
async def cmd_broadcast_start(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AdminStates.broadcast_message)
    await message.answer("Введите текст рассылки \\(следующее сообщение\\):", parse_mode="MarkdownV2")


@router.message(AdminStates.broadcast_message)
async def cmd_broadcast_send(message: Message, state: FSMContext) -> None:
    await state.clear()
    db = await get_db()
    users = await queries.get_all_users(db)
    sent = 0
    for u in users:
        try:
            await message.bot.send_message(u["telegram_id"], message.text)
            sent += 1
        except Exception:
            pass
    await message.answer(f"✅ Отправлено {sent}/{len(users)} пользователей")
