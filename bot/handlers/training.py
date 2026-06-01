import logging
import random
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext

from bot.database.db import get_db
from bot.database import queries
from bot.keyboards.inline import topic_keyboard, answer_keyboard, after_training_keyboard
from bot.keyboards.reply import get_menu_keyboard
from bot.services import claude_service, wikipedia_service
from bot.states.states import TrainingStates
from bot.utils.formatters import escape_md, format_question, format_explanation, format_today_progress

router = Router()
logger = logging.getLogger(__name__)


@router.message(F.text == "📚 Тренировка")
async def start_training(message: Message, state: FSMContext) -> None:
    await state.clear()
    db = await get_db()
    topics = await queries.get_all_topics(db)
    if not topics:
        await message.answer("⚠️ База вопросов пуста. Сообщите администратору.")
        return
    await state.set_state(TrainingStates.choosing_topic)
    await message.answer(
        "📚 *Режим тренировки*\n\nВыберите тему:",
        parse_mode="MarkdownV2",
        reply_markup=topic_keyboard(topics, prefix="training_topic"),
    )


@router.callback_query(TrainingStates.choosing_topic, F.data.startswith("training_topic:"))
async def choose_topic(callback: CallbackQuery, state: FSMContext) -> None:
    db = await get_db()
    raw_topic = callback.data.split(":", 1)[1]

    if raw_topic == "random":
        topics = await queries.get_all_topics(db)
        topic = random.choice(topics)
    else:
        topic = raw_topic

    await state.update_data(topic=topic)
    await state.set_state(TrainingStates.answering)
    await callback.answer()
    await _send_next_question(callback.message, state, callback.from_user.id)


@router.callback_query(F.data == "training:next")
async def next_question(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await _send_next_question(callback.message, state, callback.from_user.id)


@router.callback_query(F.data == "training:change_topic")
async def change_topic(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(TrainingStates.choosing_topic)
    db = await get_db()
    topics = await queries.get_all_topics(db)
    await callback.answer()
    await callback.message.answer(
        "🔄 Выберите новую тему:",
        parse_mode="MarkdownV2",
        reply_markup=topic_keyboard(topics, prefix="training_topic"),
    )


async def _send_next_question(message, state: FSMContext, user_id: int) -> None:
    db = await get_db()
    data = await state.get_data()
    topic = data.get("topic")

    recent = await queries.get_recent_training_question_ids(db, user_id, topic, limit=50)
    questions = await queries.get_random_questions(db, topic, 1, exclude_ids=recent)

    if not questions:
        await message.answer(
            f"🎉 Вы ответили на все вопросы по теме *{escape_md(topic)}*\\!\n"
            "Начнём заново с перемешанными вопросами\\.",
            parse_mode="MarkdownV2",
        )
        questions = await queries.get_random_questions(db, topic, 1)

    if not questions:
        await message.answer("⚠️ Нет вопросов по выбранной теме.")
        return

    q = questions[0]
    today_stats = await queries.get_today_training_stats(db, user_id)

    progress_line = format_today_progress(today_stats)
    text = format_question(q, index=today_stats["total"] + 1, total="∞")
    if progress_line:
        text = escape_md(progress_line) + "\n\n" + text

    await message.answer(
        text,
        parse_mode="MarkdownV2",
        reply_markup=answer_keyboard(q["id"], mode="training"),
    )


@router.callback_query(F.data.startswith("training_answer:"))
async def process_answer(callback: CallbackQuery, state: FSMContext) -> None:
    _, question_id, chosen = callback.data.split(":")
    user_id = callback.from_user.id
    db = await get_db()

    question = await queries.get_question_by_id(db, question_id)
    if not question:
        await callback.answer("Вопрос не найден.", show_alert=True)
        return

    is_correct = chosen == question["correct_answer"]
    await queries.save_training_answer(db, user_id, question_id, chosen, is_correct)

    await callback.answer("✅ Верно!" if is_correct else "❌ Неверно")

    explanation = await claude_service.get_explanation(question)
    result_text = format_explanation(explanation, is_correct, chosen, question["correct_answer"])

    await callback.message.answer(
        result_text,
        parse_mode="MarkdownV2",
        reply_markup=after_training_keyboard(),
    )

    drug_name = question.get("drug_name")
    if drug_name:
        image_bytes = await wikipedia_service.get_drug_image(drug_name)
        if image_bytes:
            try:
                await callback.message.answer_photo(
                    photo=BufferedInputFile(image_bytes, filename="drug.jpg"),
                    caption=f"*{escape_md(drug_name)}*",
                    parse_mode="MarkdownV2",
                )
            except Exception as e:
                logger.warning("Failed to send photo for %s: %s", drug_name, e)
