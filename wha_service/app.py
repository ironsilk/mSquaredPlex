import asyncio
import logging
import hashlib
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# Reuse existing business logic from the Telegram service
from telegram_service.services.download_service import (
    get_pkg_for_input,
    build_torrents_keyboard,
    perform_download,
    pkg_basic_info,
)
from telegram_service.bot_get_progress import get_progress
from utils import (
    get_movies_for_bulk_rating,
    update_many,
    Movie,
    User,
    get_my_movie_by_imdb,
    convert_imdb_id,
)
from telegram_service.bot_utils import make_movie_reply, invite_friend
from telegram_service.services.user_service import (
    load_users,
    toggle_watchlist,
    toggle_newsletter,
    generate_onetime_password,
)
import re

# Torrents fetch for imdb id
try:
    from myimdb_service.bot_watchlist import get_torrents_for_imdb_id
except Exception:
    from bot_watchlist import get_torrents_for_imdb_id

# WhatsApp client stub (we will implement the module later; fallback to console logging if missing)
try:
    from wha_service.whatsapp_client import WhatsAppClient
except Exception:
    WhatsAppClient = None

# Logging setup (similar format to Telegram service)
logging.basicConfig(
    format='[%(asctime)s] {%(filename)s:%(lineno)d} [%(name)s] [%(levelname)s] --> %(message)s',
    level=logging.INFO,
)
logger = logging.getLogger("WhaService")

app = FastAPI(title="WhatsApp Movie Service (Stub)")

# Very simple in-memory session store keyed by phone number
_sessions: Dict[str, Dict[str, Any]] = {}


def _get_session(phone: str) -> Dict[str, Any]:
    if phone not in _sessions:
        _sessions[phone] = {"state": "idle", "data": {}}
    return _sessions[phone]


def _reset_session(phone: str) -> None:
    _sessions[phone] = {"state": "idle", "data": {}}


def _phone_to_user_id(phone: str) -> int:
    """
    Stable mapping from phone number to an integer user id.
    We avoid Python's hash() because it changes per process due to hash randomization.
    """
    try:
        h = hashlib.sha1(phone.encode("utf-8")).hexdigest()
        return int(h[:8], 16)
    except Exception:
        # Fallback for unexpected encodings
        return abs(sum(ord(c) for c in phone)) % 2_000_000_000


# Outbound messaging helpers
class _StubClient:
    def send_text(self, phone: str, text: str) -> None:
        logger.info("[WHA OUT] to %s: %s", phone, text)

    def send_image(self, phone: str, image_bytes_or_path: Any, caption: Optional[str] = None) -> None:
        # For local stub we only log the intent to send an image
        logger.info("[WHA OUT IMAGE] to %s: caption=%s image=%s", phone, caption, type(image_bytes_or_path).__name__)


_client = WhatsAppClient() if WhatsAppClient else _StubClient()


def _normalize_text(text: str) -> str:
    return (text or "").strip()


def _main_menu_text() -> str:
    return (
        "Welcome! Please choose one of the options by typing the number:\n\n"
        "1) 📥 Download a movie\n"
        "2) 📈 Check download progress\n"
        "3) 🌡️ Rate a title\n\n"
        "You can also type 'help' or 'reset'."
    )


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.post("/wha/webhook")
async def webhook(request: Request) -> JSONResponse:
    """
    Minimal webhook endpoint (stub).
    Expected JSON body:
    {
      "from": "+40700000000",   # phone number (string)
      "text": "message text"    # user message text
    }

    This stub emulates WhatsApp inbound messages and dispatches flows based on state.
    """
    try:
        payload = await request.json()
    except Exception as e:
        logger.warning("Invalid JSON payload: %s", e)
        return JSONResponse({"ok": False, "error": "invalid_json"}, status_code=400)

    phone = str(payload.get("from") or payload.get("phone") or "").strip()
    text = _normalize_text(str(payload.get("text") or ""))

    if not phone:
        return JSONResponse({"ok": False, "error": "missing_from"}, status_code=400)
    if not text:
        return JSONResponse({"ok": False, "error": "missing_text"}, status_code=400)

    # Dispatch
    await _handle_message(phone, text)
    return JSONResponse({"ok": True})


async def _handle_message(phone: str, text: str) -> None:
    """
    Core dispatcher handling session state transitions and calling business logic.
    """
    session = _get_session(phone)
    state = session.get("state", "idle")
    user_id = _phone_to_user_id(phone)
    lower = text.lower()

    # Global commands
    if lower in ("start", "menu"):
        session["state"] = "idle"
        _client.send_text(phone, _main_menu_text())
        return

    if lower == "help":
        _client.send_text(
            phone,
            "Features:\n"
            "- Download a movie (type 1)\n"
            "- Check download progress (type 2)\n"
            "- Rate a title (type 3)\n\n"
            "Use 'reset' to end the current flow."
        )
        return

    if lower == "reset":
        _reset_session(phone)
        _client.send_text(phone, "Session reset. " + _main_menu_text())
        return

    # Entry points from menu
    if state == "idle":
        if lower in ("1", "download a movie", "download"):
            session["state"] = "download.awaiting_query"
            _client.send_text(
                phone,
                "Great, send an IMDB id (e.g. tt0903624), a title, or an IMDB link.\n"
                "Examples:\n"
                "- tt0903624\n"
                "- The Matrix\n"
                "- https://www.imdb.com/title/tt0133093/"
            )
            return

        if lower in ("2", "check download progress", "progress"):
            await _flow_progress(phone, user_id)
            return

        if lower in ("3", "rate a title", "rate"):
            session["state"] = "rating.choosing_mode"
            _client.send_text(phone, "Do you wish to rate a new title or seen-but-unrated movies?\nType: 'new title' or 'rate seen movies'")
            return

        if lower in ("register", "/register"):
            await _flow_register_start(phone)
            return

        if lower in ("change_watchlist", "/change_watchlist"):
            updated = toggle_watchlist(user_id)
            _client.send_text(phone, "Updated your watchlist preferences." if updated else "Could not update your watchlist preferences.")
            return

        if lower in ("change_newsletter", "/change_newsletter"):
            updated = toggle_newsletter(user_id)
            _client.send_text(phone, "Updated your newsletter preferences." if updated else "Could not update your newsletter preferences.")
            return

        if lower.startswith("generate_pass"):
            users = load_users()
            user_pkg = users.get(user_id)
            if not user_pkg or user_pkg.get("user_type") != "admin":
                _client.send_text(phone, "Permission denied. Only admins can generate tokens.")
                return

            args = lower.split()
            user_type = "user"
            if len(args) > 1 and args[1].strip() == "-admin":
                user_type = "admin"

            try:
                token = generate_onetime_password(user_type=user_type)
                _client.send_text(phone, f"Token {token} available for 24 hours")
            except Exception as e:
                logger.exception("Failed to generate one-time password: %s", e)
                _client.send_text(phone, "Error generating token.")
            return

        # Unknown at idle: show menu
        _client.send_text(phone, _main_menu_text())
        return

    # Download flow
    if state == "download.awaiting_query":
        await _flow_download_query(phone, user_id, text)
        return

    if state == "download.choosing_torrent":
        await _flow_download_choose_torrent(phone, user_id, text)
        return

    # Rating flow
    if state == "rating.choosing_mode":
        await _flow_rating_choose_mode(phone, user_id, text)
        return

    if state == "rating.awaiting_query":
        await _flow_rating_single_query(phone, user_id, text)
        return

    if state == "rating.submitting_rating":
        await _flow_rating_submit_single(phone, user_id, text)
        return

    if state == "rating.bulk_submitting":
        await _flow_rating_submit_bulk(phone, user_id, text)
        return

    # Registration flow
    if state == "register.enter_email":
        await _flow_register_email(phone, user_id, text)
        return

    if state == "register.ask_imdb":
        await _flow_register_ask_imdb(phone, user_id, text)
        return

    if state == "register.enter_imdb":
        await _flow_register_enter_imdb(phone, user_id, text)
        return

    # Fallback
    _client.send_text(phone, "I didn't understand that. " + _main_menu_text())


async def _flow_download_query(phone: str, user_id: int, query_text: str) -> None:
    session = _get_session(phone)
    _client.send_text(phone, "Just a sec until we get data about this title...")
    pkg: Optional[Dict[str, Any]] = None
    try:
        pkg = await asyncio.wait_for(
            asyncio.to_thread(get_pkg_for_input, query_text, user_id),
            timeout=20
        )
    except asyncio.TimeoutError:
        logger.warning("Timeout while resolving input for user %s", user_id)
    except Exception as e:
        logger.exception("Error resolving input '%s' for user %s: %s", query_text, user_id, e)

    if not pkg:
        _client.send_text(
            phone,
            "Couldn't find the specified movie. Check your spelling or try pasting the IMDB id or a link like tt0903624."
        )
        session["state"] = "idle"
        return

    # Send movie info with poster/caption
    try:
        caption, image = make_movie_reply(pkg)
        if caption:
            _client.send_text(phone, caption)
        else:
            _client.send_text(phone, pkg_basic_info(pkg))
        # Optionally log image presence
        try:
            if isinstance(image, (bytes, bytearray)):
                _client.send_image(phone, image, caption=caption)
            else:
                path = getattr(image, "name", None)
                if path:
                    _client.send_image(phone, path, caption=caption)
        except Exception:
            pass
    except Exception as e:
        logger.warning("Failed to compose movie reply: %s", e)
        _client.send_text(phone, "Movie info not available.")

    # Get torrents for imdb id
    torrents: List[Dict[str, Any]] = []
    try:
        torrents = await asyncio.wait_for(
            asyncio.to_thread(get_torrents_for_imdb_id, pkg["imdb"]),
            timeout=20
        ) or []
        torrents = sorted(torrents, key=lambda k: k.get("size", 0))
    except asyncio.TimeoutError:
        logger.warning("Timeout while fetching torrents for imdb %s", pkg.get("imdb"))
    except Exception as e:
        logger.exception("Error fetching torrents for imdb %s: %s", pkg.get("imdb"), e)

    if not torrents:
        _client.send_text(phone, "We couldn't find any torrents for this title right now.")
        _reset_session(phone)
        return

    # Build "keyboard" and present choices as numbered list
    keyboard_schema = build_torrents_keyboard(torrents)
    options: List[Dict[str, str]] = []
    for row in keyboard_schema:
        for btn in row:
            options.append(btn)
    # Persist options and original torrents
    session["state"] = "download.choosing_torrent"
    session["data"]["torrents"] = torrents
    session["data"]["options"] = options

    text_lines = ["Please select one of the torrents by typing its number:"]
    for idx, btn in enumerate(options, start=1):
        text_lines.append(f"{idx}) {btn.get('text')}")
    _client.send_text(phone, "\n".join(text_lines))


async def _flow_download_choose_torrent(phone: str, user_id: int, choice_text: str) -> None:
    session = _get_session(phone)
    data = session.get("data", {})
    options: List[Dict[str, str]] = data.get("options", [])
    torrents: List[Dict[str, Any]] = data.get("torrents", [])

    try:
        choice = int(choice_text.strip())
    except Exception:
        choice = 0

    if choice < 1 or choice > len(options):
        _client.send_text(phone, "Invalid selection. Please type the number of the torrent.")
        return

    btn = options[choice - 1]
    cb = btn.get("callback_data", "")
    torr_id = 0
    try:
        if cb.startswith("TORR:"):
            torr_id = int(cb.split(":", 1)[1])
    except Exception:
        torr_id = 0

    success, msg = perform_download(torr_id, torrents, user_id)
    _client.send_text(phone, msg)
    _reset_session(phone)


async def _flow_progress(phone: str, user_id: int) -> None:
    _client.send_text(phone, "Ok, retrieving data... (might be slow sometimes)")
    try:
        torrents = await asyncio.wait_for(
            asyncio.to_thread(get_progress, user_id),
            timeout=15
        )
    except asyncio.TimeoutError:
        logger.warning("Progress fetch timed out for user %s", user_id)
        _client.send_text(phone, "Timed out while fetching progress. Please try again.")
        return
    except Exception as e:
        logger.exception("Error retrieving progress for user %s: %s", user_id, e)
        _client.send_text(phone, "Error while fetching progress. Please try again later.")
        return

    if torrents:
        for torrent in torrents[:5]:
            _client.send_text(
                phone,
                f"{torrent.get('TorrentName')}\n"
                f"Resolution: {torrent.get('Resolution')}\n"
                f"Status: {torrent.get('Status')}\n"
                f"Progress: {torrent.get('Progress')}\n"
                f"ETA: {torrent.get('ETA')}"
            )
    else:
        _client.send_text(phone, "No torrents to show :(.")


async def _flow_rating_choose_mode(phone: str, user_id: int, text: str) -> None:
    session = _get_session(phone)
    lower = text.lower().strip()
    if lower in ("new title", "new", "1"):
        session["state"] = "rating.awaiting_query"
        _client.send_text(
            phone,
            "Great, send an IMDB id (e.g. tt0903624), a title, or an IMDB link.\n"
            "Examples:\n"
            "- tt0903624\n"
            "- The Matrix\n"
            "- https://www.imdb.com/title/tt0133093/"
        )
        return

    if lower in ("rate seen movies", "bulk", "2"):
        _client.send_text(phone, "Preparing movies...")
        try:
            unrated: List[Dict[str, Any]] = await asyncio.wait_for(
                asyncio.to_thread(get_movies_for_bulk_rating, user_id),
                timeout=20
            ) or []
        except asyncio.TimeoutError:
            logger.warning("Timeout retrieving unrated movies for user %s", user_id)
            _client.send_text(phone, "Timed out while preparing unrated movies. Please try again.")
            _reset_session(phone)
            return
        except Exception as e:
            logger.exception("Error retrieving unrated movies for user %s: %s", user_id, e)
            _client.send_text(phone, "Error while preparing unrated movies.")
            _reset_session(phone)
            return

        if not unrated:
            _client.send_text(phone, "You have no unrated movies!")
            _reset_session(phone)
            return

        session["data"]["unrated_queue"] = unrated
        await _rate_next_in_bulk(phone, user_id)
        return

    _client.send_text(phone, "Please type 'new title' or 'rate seen movies'.")


async def _flow_rating_single_query(phone: str, user_id: int, query_text: str) -> None:
    session = _get_session(phone)
    _client.send_text(phone, "Just a sec until we get data about this title...")
    pkg: Optional[Dict[str, Any]] = None
    try:
        pkg = await asyncio.wait_for(
            asyncio.to_thread(get_pkg_for_input, query_text, user_id),
            timeout=20
        )
    except asyncio.TimeoutError:
        logger.warning("Timeout while resolving rating input for user %s", user_id)
    except Exception as e:
        logger.exception("Error resolving input '%s' for user %s: %s", query_text, user_id, e)

    if not pkg:
        _client.send_text(
            phone,
            "Couldn't find the specified movie. Check your spelling or try pasting the IMDB id or a link like tt0903624."
        )
        return

    # Show info
    try:
        caption, image = make_movie_reply(pkg)
        if caption:
            _client.send_text(phone, caption)
        try:
            if isinstance(image, (bytes, bytearray)):
                _client.send_image(phone, image, caption=caption)
            else:
                path = getattr(image, "name", None)
                if path:
                    _client.send_image(phone, path, caption=caption)
        except Exception:
            pass
    except Exception as e:
        logger.warning("Failed to send movie poster, sending text only: %s", e)
        _client.send_text(phone, "Please choose a rating:")

    imdb_id_num = int(pkg["imdb"])
    data = session["data"]
    data["imdb"] = imdb_id_num
    data["rate_origin"] = "simple"
    session["state"] = "rating.submitting_rating"

    _client.send_text(phone, "Great, please choose a rating: 1..10\nOr type: I've changed my mind")


async def _flow_rating_submit_single(phone: str, user_id: int, input_text: str) -> None:
    session = _get_session(phone)
    data = session.get("data", {})
    imdb_id = int(data.get("imdb") or 0)
    text = _normalize_text(input_text)

    if text in [str(x) for x in range(1, 11)] and imdb_id:
        await _persist_rating_and_link(phone, user_id, imdb_id, int(text), origin=data.get("rate_origin") or "simple")
        _reset_session(phone)
        return

    if text.lower() in ("i've changed my mind", "changed", "cancel"):
        await _mark_refused(user_id, imdb_id)
        _client.send_text(phone, "Ok, no worries! I won't bother you about this title anymore.\nHave a great day!")
        _reset_session(phone)
        return

    _client.send_text(phone, "Please choose a rating 1..10 or type 'I've changed my mind'.")


async def _flow_rating_submit_bulk(phone: str, user_id: int, input_text: str) -> None:
    session = _get_session(phone)
    data = session.get("data", {})
    imdb_id = int(data.get("imdb") or 0)
    text = _normalize_text(input_text)

    if text in [str(x) for x in range(1, 11)] and imdb_id:
        await _persist_rating_and_link(phone, user_id, imdb_id, int(text), origin="multiple")
        await _rate_next_in_bulk(phone, user_id)
        return

    if text.lower() in ("skip this movie.", "skip"):
        await _mark_refused(user_id, imdb_id)
        _client.send_text(phone, "Skipped. Moving to next.")
        await _rate_next_in_bulk(phone, user_id)
        return

    if text.lower() in ("exit rating process.", "exit"):
        _client.send_text(phone, "Ok, your progress is saved, come back anytime.")
        _reset_session(phone)
        return

    _client.send_text(phone, "Please choose a rating 1..10, or type 'skip' / 'exit'.")


async def _rate_next_in_bulk(phone: str, user_id: int) -> None:
    session = _get_session(phone)
    queue: List[Dict[str, Any]] = session.get("data", {}).get("unrated_queue", [])
    if not queue:
        _client.send_text(phone, "No more movies left, good job!")
        _reset_session(phone)
        return

    movie = queue.pop(0)
    session["data"]["unrated_queue"] = queue

    # Resolve and present movie info
    pkg: Optional[Dict[str, Any]] = None
    try:
        pkg = await asyncio.wait_for(
            asyncio.to_thread(get_pkg_for_input, str(movie.get("imdb_id", "")), user_id),
            timeout=20
        )
    except asyncio.TimeoutError:
        logger.warning("Timeout resolving pkg for imdb %s", movie.get("imdb_id"))
        return await _rate_next_in_bulk(phone, user_id)
    except Exception as e:
        logger.exception("Error retrieving pkg for imdb %s: %s", movie.get("imdb_id"), e)
        return await _rate_next_in_bulk(phone, user_id)

    if not pkg:
        return await _rate_next_in_bulk(phone, user_id)

    try:
        caption, image = make_movie_reply(pkg)
        if caption:
            _client.send_text(phone, caption)
        try:
            if isinstance(image, (bytes, bytearray)):
                _client.send_image(phone, image, caption=caption)
            else:
                path = getattr(image, "name", None)
                if path:
                    _client.send_image(phone, path, caption=caption)
        except Exception:
            pass
    except Exception as e:
        logger.warning("Failed to send movie poster, sending text only: %s", e)

    session["data"]["imdb"] = int(pkg["imdb"])
    session["data"]["rate_origin"] = "multiple"
    session["state"] = "rating.bulk_submitting"

    _client.send_text(phone, "Please choose a rating 1..10\nOr type: 'Skip' or 'Exit'")


async def _persist_rating_and_link(phone: str, user_id: int, imdb_id: int, score: int, origin: str) -> None:
    item = get_my_movie_by_imdb(imdb_id, user_id)
    if item:
        item["rating_status"] = "rated in whatsapp"
        item["my_score"] = score
        # For parity we can also store a seen_date; legacy logic did this in Telegram
        try:
            import datetime
            item["seen_date"] = datetime.datetime.now()
        except Exception:
            pass
    else:
        try:
            import datetime
            seen_date = datetime.datetime.now()
        except Exception:
            seen_date = None
        item = {
            "imdb_id": imdb_id,
            "my_score": score,
            "rating_status": "rated in whatsapp",
            "user_id": user_id,
            "seen_date": seen_date,
        }
    try:
        update_many([item], Movie, Movie.id)
    except Exception as e:
        logger.warning("Failed to persist rating for user %s imdb %s: %s", user_id, imdb_id, e)

    imdb_link = f"https://www.imdb.com/title/{convert_imdb_id(imdb_id)}/"
    _client.send_text(
        phone,
        f"Ok, great! Here's a link if you also want to rate it on IMDB:\n{imdb_link}"
    )


async def _mark_refused(user_id: int, imdb_id: int) -> None:
    item = get_my_movie_by_imdb(imdb_id, user_id)
    if item:
        item["rating_status"] = "refused to rate"
        try:
            update_many([item], Movie, Movie.id)
        except Exception as e:
            logger.warning("Failed to update refused rating for user %s imdb %s: %s", user_id, imdb_id, e)
    else:
        item = {
            "imdb_id": imdb_id,
            "rating_status": "refused to rate",
            "user_id": user_id,
        }
        try:
            update_many([item], Movie, Movie.id)
        except Exception as e:
            logger.warning("Failed to insert refused rating for user %s imdb %s: %s", user_id, imdb_id, e)
# --- Registration & Preferences flows for WhatsApp (session-only) ---

async def _flow_register_start(phone: str) -> None:
    """
    Begin registration: ask for email and switch to register.enter_email state.
    """
    session = _get_session(phone)
    session["state"] = "register.enter_email"
    session["data"]["new_user"] = {}
    _client.send_text(
        phone,
        "Welcome! Please type in your email so that we can add you to our PLEX users."
    )


async def _flow_register_email(phone: str, user_id: int, text: str) -> None:
    """
    Capture and validate email, attempt PLEX invite, then ask for IMDB linkage.
    """
    session = _get_session(phone)
    email = (text or "").strip()
    if not re.fullmatch(r"[^@]+@[^@]+\.[^@]+", email):
        _client.send_text(phone, "Invalid email format. Please try again.")
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
        "telegram_chat_id": user_id,
        "telegram_name": phone,  # we don't have a display name in WhatsApp stub
        "email": email,
        "email_newsletters": True,
        "scan_watchlist": False,
        "user_type": "user",
    }
    session["data"]["new_user"] = new_user

    msg += (
        "Would you like to connect your IMDB account? In this way we'll be able to pull your movie ratings\n"
        "and warn you when you'll search for a movie you've already seen.\n"
        "We'll also scan your watchlist periodically and notify you when we'll be able to download any of the titles there.\n"
        "Type 'Yes' or 'No'."
    )
    session["state"] = "register.ask_imdb"
    _client.send_text(phone, msg)


async def _flow_register_ask_imdb(phone: str, user_id: int, text: str) -> None:
    """
    Handle IMDB linkage choice. Persist user if 'No', otherwise ask for IMDB id.
    """
    session = _get_session(phone)
    choice = (text or "").strip()
    new_user = session.get("data", {}).get("new_user", {})

    if choice == "Yes":
        session["state"] = "register.enter_imdb"
        _client.send_text(
            phone,
            "Go to your IMDB account and type here your user ID like 'ur77571297'. "
            "Also make sure that your Ratings are PUBLIC and so is your Watchlist (10 pages max).\n"
            "https://www.imdb.com/"
        )
        return

    if choice == "No":
        # Persist user
        try:
            update_many([new_user], User, User.telegram_chat_id)
            _client.send_text(phone, "Ok, that's it. Type 'menu' to begin. Enjoy!")
        except Exception as e2:
            logger.exception("Failed to register user %s: %s", new_user, e2)
            _client.send_text(phone, "Registration failed. Please try again later.")
        _reset_session(phone)
        return

    _client.send_text(phone, "Please type 'Yes' or 'No'.")


async def _flow_register_enter_imdb(phone: str, user_id: int, text: str) -> None:
    """
    Capture IMDB id digits, enable watchlist scan, persist user, and finish.
    """
    session = _get_session(phone)
    imdb_id_digits = "".join([x for x in (text or "") if x.isdigit()])
    new_user = session.get("data", {}).get("new_user", {})
    new_user["scan_watchlist"] = True
    if imdb_id_digits:
        new_user["imdb_id"] = int(imdb_id_digits)

    try:
        update_many([new_user], User, User.telegram_chat_id)
        _client.send_text(phone, "Ok, that's it. Type 'menu' to begin. Enjoy!")
    except Exception as e:
        logger.exception("Failed to register user %s: %s", new_user, e)
        _client.send_text(phone, "Registration failed. Please try again later.")
    _reset_session(phone)