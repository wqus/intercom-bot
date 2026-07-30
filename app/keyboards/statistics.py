from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

statistics_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Статистика")],
    ],
    resize_keyboard=True,
)

period_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="Сегодня"),
            KeyboardButton(text="Вчера"),
        ],
        [
            KeyboardButton(text="Неделя"),
            KeyboardButton(text="Месяц"),
        ],
        [KeyboardButton(text="Свой период")],
        [KeyboardButton(text="◀️ Назад")],
    ],
    resize_keyboard=True,
)

cancel_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Отмена")],
    ],
    resize_keyboard=True,
)