import html
import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.config import config
from bot.database.db import get_db
from bot.database import queries
from bot.services.question_loader import load_all_questions
from bot.states.states import AdminStates

router = Router()
logger = logging.getLogger(__name__)


def is_admin(user_id: int) -> bool:
    return user_id in config.admin_ids


async def _require_admin(message: Message) -> bool:
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Нет доступа.", parse_mode=None)
        return False
    return True


async def _send_chunks(message: Message, lines: list[str], limit: int = 3800) -> None:
    current, current_len = [], 0
    for line in lines:
        if current_len + len(line) + 1 > limit and current:
            await message.answer("\n".join(current), parse_mode="HTML")
            current, current_len = [], 0
        current.append(line)
        current_len += len(line) + 1
    if current:
        await message.answer("\n".join(current), parse_mode="HTML")


def _difficulty_bar(pct: float, length: int = 8) -> str:
    filled = round(float(pct) / 100 * length)
    return "█" * filled + "░" * (length - filled)


@router.message(Command("reload"))
async def cmd_reload(message: Message) -> None:
    if not await _require_admin(message):
        return
    db = await get_db()
    count = await load_all_questions(db)
    topic_counts = await queries.count_questions_by_topic(db)
    lines = [f"🔄 <b>Загрузка завершена</b>", f"Новых вопросов: <b>{count}</b>", "", "<b>Всего по темам:</b>"]
    for topic, cnt in sorted(topic_counts.items()):
        lines.append(f"• {html.escape(topic)}: {cnt}")
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("dbstats"))
async def cmd_dbstats(message: Message) -> None:
    if not await _require_admin(message):
        return
    db = await get_db()
    topic_counts = await queries.count_questions_by_topic(db)
    users = await queries.get_all_users(db)
    lines = [f"📊 <b>Статистика базы данных</b>", "", f"Пользователей: <b>{len(users)}</b>", "", "<b>Вопросов по темам:</b>"]
    for topic, cnt in sorted(topic_counts.items()):
        lines.append(f"• {html.escape(topic)}: {cnt}")
    await message.answer("\n".join(lines), parse_mode="HTML")


async def _adminstats_body(message: Message) -> None:
    db = await get_db()
    overview = await queries.get_admin_overview(db)
    training = await queries.get_training_difficulty_by_topic(db)
    exams = await queries.get_exam_stats_by_topic(db)
    hard_q = await queries.get_hardest_questions(db, limit=8)

    # Сообщение 1: Обзор
    lines = [
        "👑 <b>Статистика для владельца</b>",
        "",
        "👥 <b>Пользователи</b>",
        f"  Всего: <b>{overview['total_users']}</b>",
        f"  Активны сегодня: <b>{overview['active_today']}</b>",
        f"  Активны за 7 дней: <b>{overview['active_week']}</b>",
        "",
        "📈 <b>Активность</b>",
        f"  Ответов в тренировке: <b>{overview['total_training']}</b>",
        f"  Экзаменов завершено: <b>{overview['total_exams']}</b>",
    ]
    await message.answer("\n".join(lines), parse_mode="HTML")

    # Сообщение 2: Сложность тем в тренировке
    if training:
        lines = ["📚 <b>Тренировка — сложность тем</b> (по убыванию ошибок)", ""]
        for t in training:
            pct = t["pct"]
            bar = _difficulty_bar(pct)
            mark = "🔴" if pct < 50 else "🟡" if pct < 70 else "🟢"
            lines.append(
                f"{mark} {html.escape(t['topic'])}\n"
                f"   {bar} <b>{pct}%</b> верно ({t['correct']}/{t['total']})"
            )
        await _send_chunks(message, lines)

    # Сообщение 3: Статистика экзаменов
    if exams:
        lines = ["📝 <b>Экзамены — средний балл по темам</b>", ""]
        for e in exams:
            bar = _difficulty_bar(e["avg_pct"])
            mark = "🔴" if e["avg_pct"] < 50 else "🟡" if e["avg_pct"] < 70 else "🟢"
            lines.append(
                f"{mark} {html.escape(e['topic'])}\n"
                f"   {bar} <b>{e['avg_pct']}%</b> avg "
                f"(мин {e['min_pct']}% / макс {e['max_pct']}%, сессий: {e['sessions']})"
            )
        await _send_chunks(message, lines)

    # Сообщение 4: Сложнейшие вопросы
    if hard_q:
        lines = ["🧩 <b>Самые сложные вопросы</b> (наименьший % верных)", ""]
        for i, q in enumerate(hard_q, 1):
            q_text = html.escape(q["question"][:70]) + ("..." if len(q["question"]) > 70 else "")
            sub = f" — {html.escape(q['subtopic'])}" if q.get("subtopic") else ""
            lines.append(
                f"<b>{i}.</b> <i>{html.escape(q['topic'])}{sub}</i>\n"
                f"   {q_text}\n"
                f"   ❌ <b>{q['pct']}%</b> верно ({q['correct']}/{q['total']} ответов)"
            )
        await message.answer("\n".join(lines), parse_mode="HTML")
    elif not training and not exams:
        await message.answer("Данных пока нет — студенты ещё не занимались.", parse_mode=None)


@router.message(Command("adminstats"))
@router.message(F.text == "👑 Аналитика")
async def cmd_adminstats(message: Message) -> None:
    if not await _require_admin(message):
        return
    await _adminstats_body(message)


@router.callback_query(F.data == "admin_stats")
async def cb_admin_stats(call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Нет доступа", show_alert=True)
        return
    await call.answer()
    await _adminstats_body(call.message)


@router.message(Command("broadcast"))
async def cmd_broadcast_start(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AdminStates.broadcast_message)
    await message.answer("Введите текст рассылки (следующее сообщение):", parse_mode=None)


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
    await message.answer(f"✅ Отправлено {sent}/{len(users)} пользователей", parse_mode=None)
