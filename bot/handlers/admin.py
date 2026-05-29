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
from bot.utils.formatters import escape_md

router = Router()
logger = logging.getLogger(__name__)


def is_admin(user_id: int) -> bool:
    return user_id in config.admin_ids


async def _require_admin(message: Message) -> bool:
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Нет доступа\\.", parse_mode="MarkdownV2")
        return False
    return True


async def _send_chunks(message: Message, lines: list[str], limit: int = 3800) -> None:
    """Отправляет список строк, разбивая на сообщения если превышает limit символов."""
    current, current_len = [], 0
    for line in lines:
        if current_len + len(line) + 1 > limit and current:
            await message.answer("\n".join(current), parse_mode="MarkdownV2")
            current, current_len = [], 0
        current.append(line)
        current_len += len(line) + 1
    if current:
        await message.answer("\n".join(current), parse_mode="MarkdownV2")


@router.message(Command("reload"))
async def cmd_reload(message: Message) -> None:
    if not await _require_admin(message):
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
    if not await _require_admin(message):
        return
    db = await get_db()
    topic_counts = await queries.count_questions_by_topic(db)
    users = await queries.get_all_users(db)
    lines = [f"📊 *Статистика базы данных*", "", f"Пользователей: *{len(users)}*", "", "*Вопросов по темам:*"]
    for topic, cnt in sorted(topic_counts.items()):
        lines.append(f"• {escape_md(topic)}: {cnt}")
    await message.answer("\n".join(lines), parse_mode="MarkdownV2")


async def _adminstats_body(message: Message) -> None:
    """Отправляет полную статистику владельца в чат message."""
    db = await get_db()

    overview = await queries.get_admin_overview(db)
    training = await queries.get_training_difficulty_by_topic(db)
    exams = await queries.get_exam_stats_by_topic(db)
    hard_q = await queries.get_hardest_questions(db, limit=8)

    # ── Сообщение 1: Обзор ────────────────────────────────────────────────
    lines = [
        "👑 *Статистика для владельца*",
        "",
        "👥 *Пользователи*",
        f"  Всего: *{overview['total_users']}*",
        f"  Активны сегодня: *{overview['active_today']}*",
        f"  Активны за 7 дней: *{overview['active_week']}*",
        "",
        "📈 *Активность*",
        f"  Ответов в тренировке: *{overview['total_training']}*",
        f"  Экзаменов завершено: *{overview['total_exams']}*",
    ]
    await message.answer("\n".join(lines), parse_mode="MarkdownV2")

    # ── Сообщение 2: Сложность тем в тренировке ───────────────────────────
    if training:
        lines = ["📚 *Тренировка — сложность тем* \\(по убыванию ошибок\\)", ""]
        for t in training:
            pct = t["pct"]
            bar = _difficulty_bar(pct)
            mark = "🔴" if pct < 50 else "🟡" if pct < 70 else "🟢"
            lines.append(
                f"{mark} {escape_md(t['topic'])}\n"
                f"   {bar} *{pct}%* верно \\({t['correct']}/{t['total']}\\)"
            )
        await _send_chunks(message, lines)

    # ── Сообщение 3: Статистика экзаменов ─────────────────────────────────
    if exams:
        lines = ["📝 *Экзамены — средний балл по темам*", ""]
        for e in exams:
            bar = _difficulty_bar(e["avg_pct"])
            mark = "🔴" if e["avg_pct"] < 50 else "🟡" if e["avg_pct"] < 70 else "🟢"
            lines.append(
                f"{mark} {escape_md(e['topic'])}\n"
                f"   {bar} *{e['avg_pct']}%* avg  "
                f"\\(мин {e['min_pct']}% / макс {e['max_pct']}%, "
                f"сессий: {e['sessions']}\\)"
            )
        await _send_chunks(message, lines)

    # ── Сообщение 4: Сложнейшие вопросы ──────────────────────────────────
    if hard_q:
        lines = ["🧩 *Самые сложные вопросы* \\(наименьший % верных\\)", ""]
        for i, q in enumerate(hard_q, 1):
            q_text = escape_md(q["question"][:70]) + ("\\.\\.\\." if len(q["question"]) > 70 else "")
            sub = f" — {escape_md(q['subtopic'])}" if q.get("subtopic") else ""
            lines.append(
                f"*{i}\\.* _{escape_md(q['topic'])}{sub}_\n"
                f"   {q_text}\n"
                f"   ❌ *{q['pct']}%* верно \\({q['correct']}/{q['total']} ответов\\)"
            )
        await message.answer("\n".join(lines), parse_mode="MarkdownV2")
    elif not training and not exams:
        await message.answer("Данных пока нет — студенты ещё не занимались\\.", parse_mode="MarkdownV2")


@router.message(Command("adminstats"))
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


def _difficulty_bar(pct: float, length: int = 8) -> str:
    filled = round(float(pct) / 100 * length)
    return "█" * filled + "░" * (length - filled)


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
