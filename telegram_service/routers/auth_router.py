import logging
import re
from typing import Optional

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from bot_utils import invite_friend
from services.user_service import (
    load_users,
    toggle_watchlist,
    toggle_newsletter,
    generate_onetime_password,
)
from utils import update_many, User

logger = logging.getLogger("AuthRouter")
router = Router()


class RegisterStates(StatesGroup):
    enter_email = State()
    ask_imdb = State()
    enter_imdb = State()


def yes_no_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Yes")], [KeyboardButton(text="No")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


@router.message(Command("register"))
async def register_start(message: Message, state: FSMContext):
    """
    Start user registration: ask for email and proceed to IMDB linkage option.
    """
    await state.set_state(RegisterStates.enter_email)
    await message.answer(
        "Welcome! Please type in your email so that we can add you to our PLEX users."
    )


@router.message(RegisterStates.enter_email)
async def register_email(message: Message, state: FSMContext):
    email = (message.text or "").strip()
    if not re.fullmatch(r"[^@]+@[^@]+\.[^@]+", email):
        await message.answer("Invalid email format. Please try again.")
        return

    # Invite to PLEX server
    email_invite = False
    try:
        email_invite = invite_friend(email)
    except Exception as e:
        logger.warning("PLEX invite failed for %s: %s", email, e)

    if email_invite:
        msg = "Great! An invitation for PLEX has been sent to your email.\n"
    else:
        msg = (
            "Looks like either this email is already in our PLEX users database OR you're not planning to use PLEX.\n"
            "If this is not the case, please contact the admin.\n\n"
        )

    # Prepare user pkg
    new_user = {
        "telegram_chat_id": message.from_user.id,
        "telegram_name": message.from_user.first_name,
        "email": email,
        "email_newsletters": True,
        "scan_watchlist": False,
        "user_type": "user",
    }
    await state.update_data(new_user=new_user)

    msg += (
        "Would you like to connect your IMDB account? In this way we'll be able to pull your movie ratings\n"
        "and warn you when you'll search for a movie you've already seen.\n"
        "We'll also scan your watchlist periodically and notify you when we'll be able to download any of the titles there."
    )
    await state.set_state(RegisterStates.ask_imdb)
    await message.answer(msg, reply_markup=yes_no_keyboard())


@router.message(RegisterStates.ask_imdb)
async def register_ask_imdb(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    data = await state.get_data()
    new_user = data.get("new_user")

    if text == "Yes":
        await state.set_state(RegisterStates.enter_imdb)
        await message.answer(
            "Go to your IMDB account and copy here your user ID like 'ur77571297'. "
            "Also make sure that your Ratings are PUBLIC and so is your Watchlist (10 pages max).\n"
            "https://www.imdb.com/"
        )
        return

    if text == "No":
        # Persist user
        try:
            update_many([new_user], User, User.telegram_chat_id)
            await message.answer("Ok, that's it. Type /start to begin. Enjoy!")
        except Exception as e:
            logger.exception("Failed to register user %s: %s", new_user, e)
            await message.answer("Registration failed. Please try again later.")
        await state.clear()
        return

    await message.answer("Please choose Yes or No.", reply_markup=yes_no_keyboard())


@router.message(RegisterStates.enter_imdb)
async def register_enter_imdb(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    imdb_id_digits = "".join([x for x in text if x.isdigit()])
    data = await state.get_data()
    new_user = data.get("new_user")
    new_user["scan_watchlist"] = True
    if imdb_id_digits:
        new_user["imdb_id"] = imdb_id_digits

    try:
        update_many([new_user], User, User.telegram_chat_id)
        await message.answer("Ok, that's it. Type /start to begin. Enjoy!")
    except Exception as e:
        logger.exception("Failed to register user %s: %s", new_user, e)
        await message.answer("Registration failed. Please try again later.")
    await state.clear()


@router.message(Command("change_watchlist"))
async def change_watchlist(message: Message):
    updated = toggle_watchlist(message.from_user.id)
    if updated:
        await message.answer("Updated your watchlist preferences.")
    else:
        await message.answer("Could not update your watchlist preferences.")


@router.message(Command("change_newsletter"))
async def change_newsletter(message: Message):
    updated = toggle_newsletter(message.from_user.id)
    if updated:
        await message.answer("Updated your newsletter preferences.")
    else:
        await message.answer("Could not update your newsletter preferences.")


@router.message(Command("generate_pass"))
async def generate_password(message: Message):
    """
    Generate one-time password tokens. Only allowed for admins.
    Usage:
    /generate_pass
    /generate_pass -admin
    """
    users = load_users()
    user_pkg = users.get(message.from_user.id)
    if not user_pkg or user_pkg.get("user_type") != "admin":
        await message.answer("Permission denied. Only admins can generate tokens.")
        return

    args = (message.text or "").strip().split()
    user_type = "user"
    if len(args) > 1 and args[1].strip() == "-admin":
        user_type = "admin"

    try:
        token = generate_onetime_password(user_type=user_type)
        await message.answer(f"Token {token} available for 24 hours")
    except Exception as e:
        logger.exception("Failed to generate one-time password: %s", e)
        await message.answer("Error generating token.")