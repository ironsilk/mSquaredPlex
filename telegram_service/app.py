import asyncio
import logging
import os
from typing import List

from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, BotCommand
from aiogram.filters import Command
from keyboards.main import main_menu_keyboard
from routers.misc_router import router as misc_router
from routers.download_router import router as download_router
from routers.rating_router import router as rating_router
from routers.auth_router import router as auth_router
from routers.progress_router import router as progress_router
from services.notifier_service import start_notifier
from services.watchlist_service import start_watchlist_monitor
from utils import check_database, ensure_user_exists

# Logging setup
logging.basicConfig(
    format='[%(asctime)s] {%(filename)s:%(lineno)d} [%(name)s] [%(levelname)s] --> %(message)s',
    level=logging.DEBUG,
)
logger = logging.getLogger("AiogramMovieBot")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# Main menu keyboard is provided by keyboards.main.main_menu_keyboard


# Root router (Phase 1: minimal handlers; feature routers will be added next)
root_router = Router()


@root_router.message(Command("start"))
async def start_handler(message: Message):
    """
    Entry point: shows the main menu.
    """
    # Ensure the Telegram user exists in DB to satisfy FK constraints in later flows
    try:
        ensure_user_exists(message.from_user.id, message.from_user.full_name)
    except Exception as e:
        logger.warning("Failed to ensure user exists for %s: %s", message.from_user.id, e)

    greet = f"Hi {message.from_user.full_name}!\nPlease select one of the options or use /help."
    await message.answer(greet, reply_markup=main_menu_keyboard())

@root_router.message(Command("menu"))
async def menu_handler(message: Message):
    """
    Alias for /start to show the main menu again quickly.
    """
    await start_handler(message)


async def setup_bot_commands(bot: Bot):
    commands: List[BotCommand] = [
        BotCommand(command="start", description="Show the main menu"),
        BotCommand(command="help", description="Show help and preferences"),
        BotCommand(command="reset", description="Reset the conversation"),
        BotCommand(command="register", description="Register user (email + optional IMDB)"),
        BotCommand(command="change_watchlist", description="Toggle watchlist monitoring"),
        BotCommand(command="change_newsletter", description="Toggle newsletter emails"),
        BotCommand(command="generate_pass", description="Generate one-time token (admin)"),
    ]
    await bot.set_my_commands(commands)


async def main():
    if not TELEGRAM_TOKEN:
        raise RuntimeError("TELEGRAM_TOKEN environment variable is not set")

    # Initialize database tables if they don't exist
    try:
        check_database()
    except Exception as e:
        logger.warning("Database initialization encountered an issue: %s", e)

    bot = Bot(token=TELEGRAM_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    # Include routers
    dp.include_router(root_router)
    dp.include_router(misc_router)
    dp.include_router(auth_router)
    dp.include_router(download_router)
    dp.include_router(rating_router)
    dp.include_router(progress_router)

    await setup_bot_commands(bot)

    # Start background tasks
    notifier_task = asyncio.create_task(start_notifier(bot))
    # Watchlist monitor interval: default 3h (10800s), configurable via env
    watchlist_interval = int(os.getenv("WATCHLIST_SCAN_INTERVAL_SECONDS", "10800"))
    watchlist_task = asyncio.create_task(start_watchlist_monitor(bot, interval_seconds=watchlist_interval))

    logger.info("Starting Aiogram dispatcher polling...")
    try:
        await dp.start_polling(bot)
    finally:
        logger.info("Stopping background tasks...")
        # Cancel tasks and await graceful shutdown
        for task, name in ((notifier_task, "notifier"), (watchlist_task, "watchlist")):
            try:
                task.cancel()
            except Exception:
                logger.debug("Failed to cancel %s task (already stopped?)", name)
        for task, name in ((notifier_task, "notifier"), (watchlist_task, "watchlist")):
            try:
                await task
            except asyncio.CancelledError:
                logger.debug("%s task cancelled", name)
            except Exception as e:
                logger.debug("Error awaiting %s task shutdown: %s", name, e)


if __name__ == "__main__":
    asyncio.run(main())