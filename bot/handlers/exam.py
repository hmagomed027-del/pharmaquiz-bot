import asyncio
import logging
import random
import time
from typing import Optional
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext

from bot.database.db import get_db
from bot.database import queries
from bot.keyboards.inline import (
    topic_keyboard, exam_count_keyboard, exam_time_keyboard,
    exam_question_keyboard, after_exam_keyboard, main_menu_inline,
)
from bot.keyboards.reply import get_menu_keyboard
from bot.services import claude_service, wikipedia_service
from bot.states.states import ExamStates
from bot.utils.formatters import escape_md, format_question, format_exam_result, format_explanation

router = Router()
logger = logging.getLogger(__name__)

_timer_tasks: dict[int, asyncio.Task] = {}


@router.message(F.text == "📝 Экзамен")
async def start_exam(message: Message, state: FSMContext) -> None:
    await state.clear()
    db = await get_db()
    topics = await queries.get_all_topics(db)
    if not topics:
        await message.answer("⚠️ База вопросов пуста.")
        return
    await state.set_state(ExamStates.choosing_topic)
    await message.answer(
        "📝 *Режим экзамена*\n\nВыберите тему:",
        parse_mode="MarkdownV2",
        reply_markup=topic_keyboard(topics, prefix="exam_topic"),
    )


@router.callback_query(ExamStates.choosing_topic, F.data.startswith("exam_topic:"))
async def choose_exam_topic(callback: CallbackQuery, state: FSMContext) -> None:
    db = await get_db()
    raw = callback.data.split(":", 1)[1]
    if raw == "random":
        topics = await queries.get_all_topics(db)
        topic = random.choice(topics)
    else:
        topic = raw
    await state.update_data(topic=topic)
    await state.set_state(ExamStates.choosing_count)
    await callback.answer()
    await callback.message.answer(
        f"Тема: *{escape_md(topic)}*\n\nСколько вопросов?",
        parse_mode="MarkdownV2",
        reply_markup=exam_count_keyboard(),
    )


@router.callback_query(ExamStates.choosing_count, F.data.startswith("exam_count:"))
async def choose_exam_count(callback: CallbackQuery, state: FSMContext) -> None:
    count = int(callback.data.split(":")[1])
    await state.update_data(count=count)
    await state.set_state(ExamStates.choosing_time)
    await callback.answer()
    await callback.message.answer(
        "⏱ *Ограничение по времени:*",
        parse_mode="MarkdownV2",
        reply_markup=exam_time_keyboard(),
    )


@router.callback_query(ExamStates.choosing_time, F.data.startswith("exam_time:"))
async def choose_exam_time(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    secs = int(callback.data.split(":")[1])
    time_limit = secs if secs > 0 else None
    time_choice = None if time_limit is None else f"{secs // 60} мин"

    await callback.answer()
    data = await state.get_data()
    topic = data["topic"]
    count = data["count"]

    db = await get_db()
    questions = await queries.get_random_questions(db, topic, count)
    if not questions:
        await callback.message.answer("⚠️ Нет вопросов по этой теме.")
        await state.clear()
        return

    question_ids = [q["id"] for q in questions]
    session_id = await queries.create_exam_session(
        db, callback.from_user.id, topic, len(question_ids), time_limit, time_choice
    )

    started_at = time.time()
    await state.update_data(
        question_ids=question_ids,
        current_index=0,
        session_id=session_id,
        started_at=started_at,
        time_limit=time_limit,
        skipped=[],
    )
    await state.set_state(ExamStates.answering)

    if time_limit:
        user_id = callback.from_user.id
        task = asyncio.create_task(
            _run_timer(bot, user_id, session_id, time_limit, state)
        )
        _timer_tasks[user_id] = task

    limit_text = f"⏱ Время: *{escape_md(time_choice)}*" if time_choice else "♾ Без ограничения по времени"
    await callback.message.answer(
        f"🚀 *Экзамен начался\\!*\n\n"
        f"Тема: *{escape_md(topic)}*\n"
        f"Вопросов: *{len(question_ids)}*\n"
        f"{limit_text}\n\n"
        "Отвечайте на вопросы\\. Можно пропустить и вернуться позже\\.",
        parse_mode="MarkdownV2",
    )
    await _send_exam_question(callback.message, state)


async def _run_timer(bot: Bot, user_id: int, session_id: int,
                     seconds: int, state: FSMContext) -> None:
    try:
        warning_at = seconds - 120
        if warning_at > 0:
            await asyncio.sleep(warning_at)
            try:
                await bot.send_message(user_id, "⚠️ *Осталось 2 минуты\\!* Поторопитесь\\.",
                                       parse_mode="MarkdownV2")
            except Exception:
                pass
            await asyncio.sleep(120)
        else:
            await asyncio.sleep(seconds)
        current_state = await state.get_state()
        if current_state == ExamStates.answering:
            await bot.send_message(user_id, "⏰ *Время вышло\\!* Экзамен завершён\\.",
                                   parse_mode="MarkdownV2")
            await _finish_exam(bot, user_id, session_id, state, status="timeout")
    except asyncio.CancelledError:
        pass


async def _send_exam_question(message, state: FSMContext) -> None:
    data = await state.get_data()
    question_ids: list = data["question_ids"]
    current_index: int = data["current_index"]
    skipped: list = data.get("skipped", [])

    unanswered = [i for i in range(len(question_ids)) if i >= current_index and i not in skipped]
    if not unanswered:
        unanswered = skipped[:]

    if not unanswered:
        await _finish_exam(
            message.bot, message.chat.id, data["session_id"], state, status="completed"
        )
        return

    idx = unanswered[0]
    db = await get_db()
    q = await queries.get_question_by_id(db, question_ids[idx])
    total = len(question_ids)

    text = format_question(
        q, index=idx + 1, total=total,
        started_at=data.get("started_at"),
        time_limit=data.get("time_limit"),
    )
    await message.answer(
        text,
        parse_mode="MarkdownV2",
        reply_markup=exam_question_keyboard(q["id"], show_skip=True),
    )
    await state.update_data(current_question_idx=idx)


@router.callback_query(ExamStates.answering, F.data.startswith("exam_answer:"))
async def process_exam_answer(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    _, question_id, chosen = callback.data.split(":")
    data = await state.get_data()
    started_at = data.get("started_at", time.time())
    time_limit = data.get("time_limit")

    if time_limit and time.time() - started_at > time_limit:
        await callback.answer("Время вышло!", show_alert=True)
        return

    db = await get_db()
    question = await queries.get_question_by_id(db, question_id)
    if not question:
        await callback.answer("Вопрос не найден.", show_alert=True)
        return

    is_correct = chosen == question["correct_answer"]
    idx = data["current_question_idx"]
    session_id = data["session_id"]

    await queries.save_exam_answer(db, session_id, question_id, chosen, is_correct, False, idx)
    await callback.answer("✅" if is_correct else "❌")

    question_ids = data["question_ids"]
    skipped = data.get("skipped", [])

    next_index = idx + 1
    while next_index in skipped and next_index < len(question_ids):
        next_index += 1

    remaining_unanswered = [
        i for i in range(len(question_ids))
        if i != idx and i not in skipped and i >= data["current_index"]
    ]

    new_skipped = [s for s in skipped if s != idx]
    await state.update_data(
        current_index=next_index,
        skipped=new_skipped,
    )

    all_done = next_index >= len(question_ids) and not new_skipped
    if all_done:
        user_id = callback.from_user.id
        if user_id in _timer_tasks:
            _timer_tasks.pop(user_id).cancel()
        await _finish_exam(bot, user_id, session_id, state, status="completed")
    else:
        await _send_exam_question(callback.message, state)


@router.callback_query(ExamStates.answering, F.data.startswith("exam_skip:"))
async def skip_exam_question(callback: CallbackQuery, state: FSMContext) -> None:
    question_id = callback.data.split(":")[1]
    data = await state.get_data()
    idx = data["current_question_idx"]
    skipped = data.get("skipped", [])

    if idx not in skipped:
        skipped.append(idx)

    await state.update_data(skipped=skipped, current_index=idx + 1)
    await callback.answer("Пропущен, вернёмся позже")
    await _send_exam_question(callback.message, state)


async def _finish_exam(bot: Bot, user_id: int, session_id: int,
                       state: FSMContext, status: str) -> None:
    db = await get_db()
    data = await state.get_data()
    started_at = data.get("started_at", time.time())
    elapsed = int(time.time() - started_at)

    answers = await queries.get_exam_answers(db, session_id)
    correct_count = sum(1 for a in answers if a["is_correct"])

    await queries.finish_exam_session(db, session_id, correct_count, status, elapsed)
    await state.set_state(ExamStates.reviewing)
    await state.update_data(session_id=session_id)

    session = await queries.get_exam_session(db, session_id)
    result_text = format_exam_result(session, answers)
    has_errors = any(not a["is_correct"] for a in answers)

    await bot.send_message(
        user_id,
        result_text,
        parse_mode="MarkdownV2",
        reply_markup=after_exam_keyboard(has_errors=has_errors),
    )


@router.callback_query(ExamStates.reviewing, F.data == "exam:review_errors")
async def review_errors(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    session_id = data["session_id"]
    db = await get_db()
    answers = await queries.get_exam_answers(db, session_id)
    wrong = [a for a in answers if not a["is_correct"] and not a["is_skipped"]]

    await callback.answer()
    if not wrong:
        await callback.message.answer("🎉 Нет ошибок для разбора\\!", parse_mode="MarkdownV2",
                                      reply_markup=main_menu_inline())
        return

    await callback.message.answer(
        f"🔍 *Разбор ошибок* — {len(wrong)} вопрос\\(ов\\):",
        parse_mode="MarkdownV2",
    )

    for a in wrong:
        q = await queries.get_question_by_id(db, a["question_id"])
        if not q:
            continue
        explanation = await claude_service.get_explanation(q)
        opts = {"A": q["option_a"], "B": q["option_b"],
                "C": q["option_c"], "D": q["option_d"]}
        result_text = format_explanation(
            explanation, False, a["chosen_answer"] or "—", q["correct_answer"], opts
        )
        try:
            await callback.message.answer(result_text, parse_mode="HTML")
        except Exception as e:
            logger.error("Failed to send exam explanation for question %s: %s", q["id"], e)
            await callback.message.answer("⚠️ Объяснение временно недоступно.")

        if q.get("drug_name"):
            image_bytes = await wikipedia_service.get_drug_image(q["drug_name"])
            if image_bytes:
                try:
                    await callback.message.answer_photo(
                        photo=BufferedInputFile(image_bytes, filename="drug.jpg"),
                        caption=f"*{escape_md(q['drug_name'])}*",
                        parse_mode="MarkdownV2",
                    )
                except Exception as e:
                    logger.warning("Photo error: %s", e)

    await callback.message.answer(
        "✅ Разбор завершён\\.",
        parse_mode="MarkdownV2",
        reply_markup=main_menu_inline(),
    )


@router.callback_query(ExamStates.reviewing, F.data == "exam:again")
async def exam_again(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    db = await get_db()
    topics = await queries.get_all_topics(db)
    await callback.answer()
    await state.set_state(ExamStates.choosing_topic)
    await callback.message.answer(
        "📝 *Новый экзамен* — выберите тему:",
        parse_mode="MarkdownV2",
        reply_markup=topic_keyboard(topics, prefix="exam_topic"),
    )
