import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from keyboards.main import main_menu_keyboard

logger = logging.getLogger("MiscRouter")
router = Router()


@router.message(Command("help"))
async def help_command(message: Message):
    """
    Displays info on how to use the bot.
    Phase 1: minimal help; will be expanded in later phases with preferences toggles.
    """
    await message.answer(
        "Type /start to show the main menu.\n\n"
        "Features available:\n"
        "- 📥 Download a movie\n"
        "- 🌡️ Rate a title\n\n"
        "If something goes wrong, use /reset."
    )


@router.message(Command("reset"))
async def reset_command(message: Message):
    """
    End conversation by command: send farewell and show how to start again.
    """
    await message.answer("See you next time. Type /start to get started again.", reply_markup=main_menu_keyboard())