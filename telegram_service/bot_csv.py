"""
Deprecated: CSV import/export has been removed from the Telegram service.
This module is retained only to prevent accidental import errors.

Do NOT use this module for new code.
"""

import logging

_logger = logging.getLogger("BotCSVShim")
_logger.warning(
    "telegram_service.bot_csv is deprecated. CSV import/export has been removed."
)


async def csv_upload_handler(*args, **kwargs):
    """
    Deprecated no-op. CSV upload handler removed.
    """
    try:
        context = kwargs.get("context") or (args[0] if args else None)
        if context and getattr(context, "bot", None):
            user = None
            try:
                user = context.job.context.get("user")
            except Exception:
                pass
            await context.bot.send_message(
                chat_id=user,
                text="CSV import has been removed."
            )
    except Exception:
        pass
    return None


async def csv_download_handler(*args, **kwargs):
    """
    Deprecated no-op. CSV download handler removed.
    """
    try:
        context = kwargs.get("context") or (args[0] if args else None)
        if context and getattr(context, "bot", None):
            user = None
            try:
                user = context.job.context.get("user")
            except Exception:
                pass
            await context.bot.send_message(
                chat_id=user,
                text="CSV export has been removed."
            )
    except Exception:
        pass
    return None
