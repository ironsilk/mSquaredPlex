import asyncio
import logging
import os
from collections import Counter
from typing import List, Dict

import requests
from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter

from utils import (
    update_many,
    convert_imdb_id,
    get_torr_quality,
    get_new_watchlist_items,
    get_from_watchlist_by_user_telegram_id_and_imdb,
    Watchlist,
    get_torr_name,
)

logger = logging.getLogger("WatchlistService")

# Read tracker/env configuration
API_URL = os.getenv("API_URL")
USER = os.getenv("FL_USER")
PASSKEY = os.getenv("PASSKEY")
MOVIE_HDRO = os.getenv("MOVIE_HDRO")
MOVIE_4K = os.getenv("MOVIE_4K")

async def start_watchlist_monitor(bot: Bot, interval_seconds: int = 10800) -> None:
    logger.info("Starting watchlist monitor background task with interval=%ss", interval_seconds)
    while True:
        try:
            await _poll_and_notify_watchlist(bot)
        except Exception as e:
            logger.exception("Error in watchlist polling loop: %s", e)
        await asyncio.sleep(interval_seconds)

async def _poll_and_notify_watchlist(bot: Bot) -> None:
    watchlist_items = get_new_watchlist_items() or []
    if not watchlist_items:
        logger.debug("Watchlist monitor: no new items")
        return

    for item in watchlist_items:
        try:
            imdb_id = item.get("imdb_id")
            tg_id = item.get("user_id")
            excluded = item.get("excluded_torrents")
            is_downloaded = item.get("is_downloaded")
            logger.debug("Watchlist: imdb_id=%s user_id=%s excluded=%s is_downloaded=%s",
                         imdb_id, tg_id, bool(excluded), is_downloaded)

            torrents = get_torrents_for_imdb_id(imdb_id)
            logger.info("Watchlist imdb %s: fetched %s torrents before filters", imdb_id, len(torrents))
            torrents = sorted(torrents, key=lambda k: k.get("size", 0))

            if excluded:
                pre = len(torrents)
                torrents = [x for x in torrents if x.get("id") not in excluded]
                logger.debug("Watchlist: excluded_torrents filter removed %s items", pre - len(torrents))
            if is_downloaded:
                pre = len(torrents)
                torrents = [x for x in torrents if str(x.get("resolution")) != is_downloaded]
                logger.debug("Watchlist: is_downloaded filter removed %s items", pre - len(torrents))

            if torrents:
                # Compose message
                name = torrents[0].get("name")
                safe_title = get_torr_name(name) if name else "Movie"
                msg = (
                    "Hi there! WATCHLIST ALERT!\n"
                    f"🎞️ {safe_title}\n"
                    f"has {len(torrents)} download candidates\n"
                    f"📥 /WatchMatch_{imdb_id} (download)\n\n"
                    f"❌ /UnWatchMatch_{imdb_id} (forget movie)"
                )
                if is_downloaded:
                    msg += f"\n🚨 Movie aleady exists in PLEX, quality: {is_downloaded}"

                try:
                    await bot.send_message(chat_id=tg_id, text=msg)
                    update_watchlist_item_status(imdb_id, tg_id, "notification sent")
                except TelegramRetryAfter as e:
                    wait_s = int(getattr(e, "retry_after", 3))
                    logger.warning("Rate limited when notifying user %s; waiting %ss then retrying", tg_id, wait_s)
                    await asyncio.sleep(wait_s)
                    try:
                        await bot.send_message(chat_id=tg_id, text=msg)
                        update_watchlist_item_status(imdb_id, tg_id, "notification sent")
                    except Exception as e2:
                        logger.exception("Failed to notify user %s for imdb %s after retry: %s", tg_id, imdb_id, e2)
                except Exception as e:
                    logger.exception("Failed to notify user %s for imdb %s: %s", tg_id, imdb_id, e)
            else:
                logger.debug("Watchlist: no torrents to notify for imdb %s (excluded=%s, is_downloaded=%s)",
                             imdb_id, excluded, is_downloaded)
        except Exception as e:
            logger.exception("Watchlist: error processing item %s: %s", item, e)

def get_torrents_for_imdb_id(idd):
    imdb_q = convert_imdb_id(idd)
    params = {
        "username": USER,
        "passkey": PASSKEY,
        "action": "search-torrents",
        "type": "imdb",
        "query": imdb_q,
    }
    include_cat = False
    if MOVIE_HDRO and MOVIE_4K:
        try:
            params["category"] = ",".join([str(MOVIE_HDRO), str(MOVIE_4K)])
            include_cat = True
        except Exception:
            include_cat = False

    safe_url = f"{API_URL}?action=search-torrents&type=imdb&query={imdb_q}&category={'yes' if include_cat else 'no'}"
    if not include_cat:
        logger.warning("Tracker request: category omitted due to missing MOVIE_HDRO/MOVIE_4K envs")
    logger.debug("Tracker env: API_URL set=%s, USER set=%s, PASSKEY set=%s",
                 bool(API_URL), bool(USER), bool(PASSKEY))
    logger.debug("Tracker request: imdb=%s, include_category=%s, MOVIE_HDRO=%s, MOVIE_4K=%s, url=%s",
                 imdb_q, include_cat, MOVIE_HDRO, MOVIE_4K, safe_url)

    try:
        r = requests.get(url=API_URL, params=params, timeout=15)
    except Exception as e:
        logger.error("Tracker request failed: %s", type(e).__name__)
        return []

    content_type = r.headers.get("Content-Type", "")
    logger.debug("Tracker response: status=%s, ct=%s", r.status_code, content_type)
    if r.status_code != 200:
        body_head = ""
        try:
            body_head = (r.text or "")[:200]
        except Exception:
            body_head = ""
        logger.warning("Tracker non-200: %s, ct=%s, body_head=%s", r.status_code, content_type, body_head)
        return []

    try:
        data = r.json()
    except Exception:
        head = ""
        try:
            head = (r.text or "")[:200]
        except Exception:
            head = ""
        logger.warning("Tracker JSON parse failed; ct=%s; body_head=%s", content_type, head)
        return []

    items = None
    if isinstance(data, list):
        items = data
        logger.debug("Tracker JSON list with %s items", len(items))
    elif isinstance(data, dict):
        logger.debug("Tracker JSON dict keys=%s", list(data.keys())[:8])
        for key in ("results", "data", "torrents", "items", "response"):
            v = data.get(key)
            if isinstance(v, list):
                items = v
                logger.debug("Tracker wrapper key '%s' contains %s items", key, len(items))
                break
        if items is None:
            logger.warning("Tracker JSON dict without list under known keys")
            return []
    else:
        logger.warning("Tracker JSON unexpected type: %s", type(data).__name__)
        return []

    sample = []
    for x in items[:3]:
        if isinstance(x, dict):
            sample.append({
                "id": x.get("id"),
                "category": x.get("category"),
                "name_head": (x.get("name") or "")[:80]
            })
    logger.debug("Tracker items sample (first 3): %s", sample)

    try:
        cat_counts = Counter(str(xx.get("category", "")) for xx in items if isinstance(xx, dict))
        logger.debug("Tracker category distribution: %s", dict(cat_counts))
    except Exception:
        logger.debug("Could not compute category distribution")

    response = []
    non_dict = 0
    missing_name = 0
    filtered_non_remux_4k = 0

    for x in items:
        if not isinstance(x, dict):
            non_dict += 1
            continue
        name = x.get("name")
        if not name:
            missing_name += 1
            continue
        cat = str(x.get("category", ""))

        if str(MOVIE_4K) and cat == str(MOVIE_4K):
            if "remux" not in name.lower():
                filtered_non_remux_4k += 1
                continue

        try:
            x["resolution"] = get_torr_quality(name)
        except Exception:
            x["resolution"] = None

        response.append(x)

    logger.debug("Tracker filtering summary: non_dict=%s, missing_name=%s, filtered_non_remux_4k=%s, accepted=%s",
                 non_dict, missing_name, filtered_non_remux_4k, len(response))
    logger.debug("Tracker items accepted after filters: %s", len(response))
    logger.info("Tracker torrents for %s: got %s valid items", idd, len(response))
    return response

def update_watchlist_item_status(movie_id, tg_id, new_status):
    watchlist_item = get_from_watchlist_by_user_telegram_id_and_imdb(movie_id, tg_id)
    if watchlist_item:
        update_many([{
            "id": watchlist_item["id"],
            "imdb_id": movie_id,
            "user_id": tg_id,
            "status": new_status,
        }], Watchlist, Watchlist.id)