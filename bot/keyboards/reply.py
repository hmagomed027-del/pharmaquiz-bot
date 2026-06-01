from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📚 Тренировка"), KeyboardButton(text="📝 Экзамен")],
            [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="🔔 Напоминания")],
            [KeyboardButton(text="ℹ️ Помощь")],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def admin_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📚 Тренировка"), KeyboardButton(text="📝 Экзамен")],
            [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="🔔 Напоминания")],
            [KeyboardButton(text="ℹ️ Помощь"), KeyboardButton(text="👑 Аналитика")],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def get_menu_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    from bot.config import config
    return admin_menu_keyboard() if user_id in config.admin_ids else main_menu_keyboard()
