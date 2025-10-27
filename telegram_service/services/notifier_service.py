import asyncio
import logging
from typing import Dict, List

from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter

from utils import (
    make_client,
    get_requested_torrents_for_tgram_user,
    update_torrent_status,
    get_torr_name,
    update_torrent_status_by_hash,
    update_torrent_status_by_pk,
)
from bot_utils import get_telegram_users

logger = logging.getLogger("NotifierService")


async def start_notifier(bot: Bot, interval_seconds: int = 60) -> None:
    """
    Background notifier that checks Transmission and DB for completed torrents
    and immediately sends Telegram alerts, then marks them as notified to deduplicate.

    Uses:
    - get_telegram_users() to iterate users
    - get_requested_torrents_for_tgram_user(user_id) to fetch torrents
    - Transmission client via make_client()
    - update_torrent_status(db_torr_id, 'user notified (telegram)') to mark notified
    """
    logger.info("Starting notifier background task with interval=%ss", interval_seconds)
    while True:
        try:
            await _poll_and_notify(bot)
        except Exception as e:
            logger.exception("Error in notifier polling loop: %s", e)
        await asyncio.sleep(interval_seconds)


async def _poll_and_notify(bot: Bot) -> None:
    users: Dict[int, Dict] = get_telegram_users()  # tg_id -> info
    if not users:
        return

    client = make_client()
    try:
        # Offload synchronous Transmission call to a worker thread and bound with timeout
        client_torrents_raw = await asyncio.wait_for(
            asyncio.to_thread(client.get_torrents),
            timeout=15
        )
    except Exception as e:
        logger.warning("Failed to fetch torrents from Transmission client: %s", e)
        return

    client_torrents = {x.hashString: x for x in client_torrents_raw}
    client_torrents_names = {x.hashString: x.name for x in client_torrents_raw}

    for tg_id in users.keys():
        torrents = _get_active_torrents_for_user(tg_id)
        if not torrents:
            continue

        for t in torrents:
            hash_str = t.get("torr_hash")
            if not hash_str:
                continue
            # If Transmission knows about this torrent, check completion
            if hash_str in client_torrents:
                torr_resp = client_torrents[hash_str]
                try:
                    left = torr_resp.left_until_done
                    total = torr_resp.total_size or 1
                    completed = left == 0 or (left / total) <= 0.00001
                except Exception as e:
                    logger.warning("Error computing completion for hash %s: %s", hash_str, e)
                    completed = False
            else:
                # If client no longer has it, rely on DB status
                completed = t.get("status") == "seeding"

            if completed and t.get("status") not in ["user notified (telegram)", "seeding"]:
                # Compose message
                name = client_torrents_names.get(hash_str)
                safe_name = get_torr_name(name) if name else "Movie"
                resolution = t.get("resolution")
                msg = (
                    f"✅ Download completed!\n"
                    f"{safe_name}\n"
                    f"Resolution: {resolution}p\n"
                    f"Enjoy your movie."
                )
                try:
                    await bot.send_message(chat_id=tg_id, text=msg)
                    # Persist dedup status with robust fallbacks
                    torr_id_val = t.get("torr_id")
                    rows = 0
                    if torr_id_val is not None:
                        res = update_torrent_status(torr_id_val, "user notified (telegram)")
                        rows = int(getattr(res, "rowcount", 0) or 0)
                        logger.debug("Notifier: update by torr_id=%s affected %s rows", torr_id_val, rows)
                    if rows == 0 and hash_str:
                        res = update_torrent_status_by_hash(hash_str, "user notified (telegram)")
                        rows = int(getattr(res, "rowcount", 0) or 0)
                        logger.debug("Notifier: update by torr_hash=%s affected %s rows", hash_str, rows)
                    if rows == 0 and t.get("id") is not None:
                        res = update_torrent_status_by_pk(t.get("id"), "user notified (telegram)")
                        rows = int(getattr(res, "rowcount", 0) or 0)
                        logger.debug("Notifier: update by pk id=%s affected %s rows", t.get("id"), rows)
                    if rows == 0:
                        logger.warning(
                            "Notifier: Failed to persist notified status for torrent; keys: torr_id=%s torr_hash=%s pk=%s",
                            torr_id_val, hash_str, t.get("id")
                        )
                except TelegramRetryAfter as e:
                    # Respect Telegram rate limits and retry once after waiting
                    wait_s = int(getattr(e, "retry_after", 3))
                    logger.warning("Rate limited when notifying user %s; waiting %ss then retrying", tg_id, wait_s)
                    await asyncio.sleep(wait_s)
                    try:
                        await bot.send_message(chat_id=tg_id, text=msg)
                        # Repeat persistence with fallbacks after retry
                        torr_id_val = t.get("torr_id")
                        rows = 0
                        if torr_id_val is not None:
                            res = update_torrent_status(torr_id_val, "user notified (telegram)")
                            rows = int(getattr(res, "rowcount", 0) or 0)
                            logger.debug("Notifier(retry): update by torr_id=%s affected %s rows", torr_id_val, rows)
                        if rows == 0 and hash_str:
                            res = update_torrent_status_by_hash(hash_str, "user notified (telegram)")
                            rows = int(getattr(res, "rowcount", 0) or 0)
                            logger.debug("Notifier(retry): update by torr_hash=%s affected %s rows", hash_str, rows)
                        if rows == 0 and t.get("id") is not None:
                            res = update_torrent_status_by_pk(t.get("id"), "user notified (telegram)")
                            rows = int(getattr(res, "rowcount", 0) or 0)
                            logger.debug("Notifier(retry): update by pk id=%s affected %s rows", t.get("id"), rows)
                        if rows == 0:
                            logger.warning(
                                "Notifier(retry): Failed to persist notified status; keys: torr_id=%s torr_hash=%s pk=%s",
                                torr_id_val, hash_str, t.get("id")
                            )
                    except Exception as e2:
                        logger.exception(
                            "Failed to notify user %s for torrent %s (db id %s) after retry: %s",
                            tg_id, hash_str, t.get("id"), e2
                        )
                except Exception as e:
                    logger.exception(
                        "Failed to notify user %s for torrent %s (db id %s): %s",
                        tg_id, hash_str, t.get("id"), e
                    )


def _get_active_torrents_for_user(user_id: int) -> List[Dict]:
    """
    Fetch torrents for a user and filter out removed or already-notified entries.
    """
    try:
        torrents = get_requested_torrents_for_tgram_user(user_id)
        if not torrents:
            return []
        return [x for x in torrents if x.get("status") not in ["removed", "user notified (email)", "user notified (telegram)"]]
    except Exception as e:
        logger.warning("Error retrieving torrents for user %s: %s", user_id, e)
        return []