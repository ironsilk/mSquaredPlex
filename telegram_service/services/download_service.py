import logging
import re
import time
from typing import Dict, List, Optional, Tuple

from bot_utils import make_movie_reply, get_movie_from_all_databases, search_imdb_title, update_torr_db
from utils import send_torrent, compose_link, ensure_user_exists

logger = logging.getLogger("DownloadService")


def parse_imdb_input(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse user text into an imdb_id (digits only) or a title string.
    Accepts:
    - ttNNNNNNN
    - NNNNNNN (digits only)
    - https://www.imdb.com/title/ttNNNNNNN/
    Returns (imdb_id_digits, title_text)
    """
    if not text:
        return None, None

    s = text.strip()

    # Pure digits (allow at least 5 to avoid noise)
    m_digits = re.fullmatch(r"\d{5,}", s)
    if m_digits:
        return m_digits.group(0).lstrip("0"), None

    # IMDB ID with tt prefix (mandatory 'tt')
    m_id = re.fullmatch(r"(?i)tt(\d+)", s)
    if m_id:
        return m_id.group(1).lstrip("0"), None

    # Try to extract imdb id from URL
    m_url = re.search(r"imdb\.com/title/tt(\d+)", s, flags=re.IGNORECASE)
    if m_url:
        return m_url.group(1).lstrip("0"), None

    # Fallback to title text
    return None, s


def get_pkg_for_input(text: str, telegram_id: int) -> Optional[Dict]:
    """
    Resolve user input into a movie package using:
    - direct IMDB id
    - IMDB URL
    - title search via Cinemagoer
    """
    imdb_id, title_text = parse_imdb_input(text)
    if imdb_id:
        return get_movie_from_all_databases(imdb_id, telegram_id)

    if title_text:
        movies = search_imdb_title(title_text)
        if isinstance(movies, str):
            # IMDB library error or similar
            logger.warning("IMDB library error for search '%s': %s", title_text, movies)
            return None
        for candidate in movies:
            pkg = get_movie_from_all_databases(candidate["id"], telegram_id)
            if pkg:
                return pkg
    return None


def build_torrents_keyboard(torrents: List[Dict]) -> List[List[Dict[str, str]]]:
    """
    Build inline keyboard schema for aiogram: a nested list of buttons,
    each button is dict(text, callback_data). We will wrap this into aiogram types in router.
    Safely handles missing fields.
    """
    keyboard: List[List[Dict[str, str]]] = []
    for item in sorted(torrents, key=lambda k: (k.get("size") or 0)):
        resolution = item.get("resolution") or "N/A"
        size_bytes = item.get("size") or 0
        size_gb = f"{round(size_bytes / 1_000_000_000, 2)}" if size_bytes else "?"
        seeders = item.get("seeders") or 0
        leechers = item.get("leechers") or 0
        torr_id = item.get("id")
        if torr_id is None:
            # skip malformed entries
            continue
        text = (
            f"🖥 Q: {resolution}"
            f"  🗳 S: {size_gb} GB"
            f"  🌱 S/P: {seeders}/{leechers}"
        )
        keyboard.append([{"text": text, "callback_data": f"TORR:{torr_id}"}])
    # Add "None" option
    keyboard.append([{"text": "None, thanks", "callback_data": "TORR:0"}])
    return keyboard


def _send_torrent_with_retry(torr_id: int, retries: int = 3, delay_seconds: float = 1.5):
    """
    Compose link and send torrent to Transmission with simple retries for transient failures.
    """
    last_exc = None
    link = compose_link(torr_id)
    for attempt in range(1, retries + 1):
        try:
            return send_torrent(link)
        except Exception as e:
            last_exc = e
            logger.warning("Attempt %s/%s failed to send torrent %s: %s", attempt, retries, torr_id, e)
            if attempt < retries:
                time.sleep(delay_seconds)
    # all retries failed
    raise last_exc


def perform_download(torrent_id: int, pkg_torrents: List[Dict], telegram_id: int) -> Tuple[bool, str]:
    """
    Send torrent to Transmission and update DB with request status.
    Returns (success, message)
    """
    if torrent_id == 0:
        return False, "Ok, not downloading. You can add to watchlist from future flows."

    try:
        torr = [x for x in pkg_torrents if str(x["id"]) == str(torrent_id)][0]
    except IndexError:
        return False, "Invalid selection. Please try again."

    try:
        torr_client_resp = _send_torrent_with_retry(torr["id"])
    except Exception as e:
        logger.error("Error on torrent send after retries: %s", e)
        return False, "Download failed, please check logs and try again."

    try:
        # Ensure the User row exists to satisfy FK constraints before writing torrent entry
        ensure_user_exists(telegram_id)
        update_torr_db(torr, torr_client_resp, telegram_id)
    except Exception as e:
        logger.warning("Error updating torrent DB for user %s: %s", telegram_id, e)

    return True, "Download started, have a great day!"


def pkg_basic_info(pkg: Dict) -> str:
    """
    Compose a concise message text for the movie package.
    Uses make_movie_reply to build caption; returns text only.
    """
    caption, _image = make_movie_reply(pkg)
    return caption or "No info about this movie, strange."