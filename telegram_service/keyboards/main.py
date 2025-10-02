from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    """
    Main menu keyboard (cleaned: removed Netflix upload and Download my movies).
    Matches the simplified menu described in the rewrite plan.
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📥 Download a movie")],
            [KeyboardButton(text="🌡️ Rate a title")],
            [KeyboardButton(text="📊 Download progress")],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def rating_keyboard() -> ReplyKeyboardMarkup:
    """
    Keep the current rating keyboard layout for single-title rating.
    Mirrors the legacy layout in [python.rate_keyboard](telegram_service/bot.py:87) with aiogram types.
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="1"), KeyboardButton(text="2")],
            [KeyboardButton(text="3"), KeyboardButton(text="4")],
            [KeyboardButton(text="5"), KeyboardButton(text="6")],
            [KeyboardButton(text="7"), KeyboardButton(text="8")],
            [KeyboardButton(text="9"), KeyboardButton(text="10")],
            [KeyboardButton(text="I've changed my mind")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def rating_keyboard_bulk() -> ReplyKeyboardMarkup:
    """
    Keep the current bulk rating keyboard layout.
    Mirrors the legacy layout in [python.rate_keyboard_bulk](telegram_service/bot.py:95) with aiogram types.
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="1"), KeyboardButton(text="2")],
            [KeyboardButton(text="3"), KeyboardButton(text="4")],
            [KeyboardButton(text="5"), KeyboardButton(text="6")],
            [KeyboardButton(text="7"), KeyboardButton(text="8")],
            [KeyboardButton(text="9"), KeyboardButton(text="10")],
            [KeyboardButton(text="Skip this movie.")],
            [KeyboardButton(text="Exit rating process.")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )