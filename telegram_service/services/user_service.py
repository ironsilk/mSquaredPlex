import datetime
import logging
from random import randint

import sqlalchemy

from bot_utils import get_telegram_users
from utils import (
    update_many,
    User,
    insert_onetimepasswords,
)

logger = logging.getLogger("UserService")


def load_users():
    """
    Return a fresh snapshot of Telegram users keyed by telegram_chat_id.
    """
    try:
        return get_telegram_users()
    except Exception as e:
        logger.exception("Failed to load users: %s", e)
        return {}


def toggle_watchlist(chat_id: int) -> bool:
    """
    Toggle scan_watchlist for the given user and persist.
    Returns True if updated, False otherwise.
    """
    users = load_users()
    if chat_id not in users:
        logger.warning("toggle_watchlist: user %s not found", chat_id)
        return False
    pkg = users[chat_id]
    pkg["telegram_chat_id"] = chat_id
    if pkg.get("scan_watchlist") == 0:
        pkg["scan_watchlist"] = 1
    else:
        pkg["scan_watchlist"] = 0
    try:
        update_many([pkg], User, User.telegram_chat_id)
        return True
    except Exception as e:
        logger.exception("toggle_watchlist: failed to update user %s: %s", chat_id, e)
        return False


def toggle_newsletter(chat_id: int) -> bool:
    """
    Toggle email_newsletters for the given user and persist.
    Returns True if updated, False otherwise.
    """
    users = load_users()
    if chat_id not in users:
        logger.warning("toggle_newsletter: user %s not found", chat_id)
        return False
    pkg = users[chat_id]
    pkg["telegram_chat_id"] = chat_id
    if pkg.get("email_newsletters") == 0:
        pkg["email_newsletters"] = 1
    else:
        pkg["email_newsletters"] = 0
    try:
        update_many([pkg], User, User.telegram_chat_id)
        return True
    except Exception as e:
        logger.exception("toggle_newsletter: failed to update user %s: %s", chat_id, e)
        return False


def generate_onetime_password(user_type: str = "user") -> int:
    """
    Generate and insert a one-time password valid for 24 hours.
    Returns the numeric token.
    Retries on collision.
    """
    def _insert_pwd(pwd):
        try:
            insert_onetimepasswords(pwd)
        except sqlalchemy.exc.IntegrityError:
            pwd["password"] = randint(10000, 99999)
            return _insert_pwd(pwd)
        return pwd["password"]

    pwd = {
        "password": randint(10000, 99999),
        "expiry": datetime.datetime.now() + datetime.timedelta(days=1),
        "user_type": user_type,
    }
    return _insert_pwd(pwd)