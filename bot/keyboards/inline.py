from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

TOPIC_EMOJI = {
    "ПНС": "🧠",
    "ЦНС": "💊",
    "ССС": "❤️",
    "Дыхательная система": "🫁",
    "Пищеварительная система": "🍏",
    "Химиотерапия": "🧬",
    "Рецептура": "📋",
}


def topic_keyboard(topics: list[str], prefix: str = "topic") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for t in topics:
        emoji = TOPIC_EMOJI.get(t, "📌")
        builder.button(text=f"{emoji} {t}", callback_data=f"{prefix}:{t}")
    builder.button(text="🎲 Случайная тема", callback_data=f"{prefix}:random")
    builder.adjust(2)
    return builder.as_markup()


def answer_keyboard(question_id: str, mode: str = "training") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for letter in ("A", "B", "C", "D"):
        builder.button(text=letter, callback_data=f"{mode}_answer:{question_id}:{letter}")
    builder.adjust(2)
    return builder.as_markup()


def after_training_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➡️ Следующий вопрос", callback_data="training:next")
    builder.button(text="🔄 Сменить тему", callback_data="training:change_topic")
    builder.button(text="🏠 Главное меню", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()


def exam_count_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for n in (10, 20, 30):
        builder.button(text=str(n), callback_data=f"exam_count:{n}")
    builder.adjust(3)
    return builder.as_markup()


def exam_time_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    options = [("10 мин", 600), ("20 мин", 1200), ("30 мин", 1800), ("♾ Без лимита", 0)]
    for label, secs in options:
        builder.button(text=label, callback_data=f"exam_time:{secs}")
    builder.adjust(2)
    return builder.as_markup()


def exam_question_keyboard(question_id: str, show_skip: bool = True) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for letter in ("A", "B", "C", "D"):
        builder.button(text=letter, callback_data=f"exam_answer:{question_id}:{letter}")
    builder.adjust(2)
    if show_skip:
        builder.button(text="⏭ Пропустить", callback_data=f"exam_skip:{question_id}")
        builder.adjust(2, 1)
    return builder.as_markup()


def after_exam_keyboard(has_errors: bool = True) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if has_errors:
        builder.button(text="🔍 Разбор ошибок", callback_data="exam:review_errors")
    builder.button(text="🔁 Ещё раз", callback_data="exam:again")
    builder.button(text="🏠 Главное меню", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()


def main_menu_inline() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🏠 Главное меню", callback_data="main_menu")
    return builder.as_markup()
