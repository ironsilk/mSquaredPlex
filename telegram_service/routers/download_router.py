import logging
import asyncio
from typing import List, Dict, Any

from aiogram import Router, F
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BufferedInputFile,
    FSInputFile,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from services.download_service import (
    get_pkg_for_input,
    build_torrents_keyboard,
    perform_download,
    parse_imdb_input,
)
from bot_utils import make_movie_reply, search_imdb_title, add_to_watchlist
from utils import get_user_by_tgram_id, deconvert_imdb_id, ensure_user_exists, check_one_against_torrents_by_imdb
from services.plex_service import plex_has_movie_by_imdb

from services.watchlist_service import get_torrents_for_imdb_id

router = Router()
logger = logging.getLogger("DownloadRouter")


class DownloadStates(StatesGroup):
    awaiting_query = State()
    choosing_title = State()
    choosing_torrent = State()
    deciding_watchlist = State()
    confirm_redownload = State()


@router.message(F.text == "📥 Download a movie")
async def prompt_movie_query(message: Message, state: FSMContext):
    """
    Entry into the download flow: prompt user for ID/link/title and set FSM state.
    """
    await state.set_state(DownloadStates.awaiting_query)
    await message.answer(
        "Great, send an IMDB id (e.g. tt0903624), a title, or an IMDB link.\n"
        "Example inputs:\n"
        "- tt0903624\n"
        "- The Matrix\n"
        "- https://www.imdb.com/title/{movie_id_here}/"
    )


@router.message(DownloadStates.awaiting_query)
async def handle_movie_query(message: Message, state: FSMContext):
    """
    Parse input. If it's a direct IMDB id/link, resolve and proceed to torrents.
    If it's a title, start a Yes/No/Exit candidate confirmation loop.
    """
    await message.answer("Just a sec until we get data about this title...")
    imdb_id, title_text = parse_imdb_input(message.text)

    if imdb_id:
        # Direct path (id or imdb link) -> resolve pkg and proceed to torrents (legacy behavior)
        pkg = None
        try:
            pkg = await asyncio.wait_for(
                asyncio.to_thread(get_pkg_for_input, message.text, message.from_user.id),
                timeout=20
            )
        except asyncio.TimeoutError:
            logger.warning("Timeout while resolving input for user %s (direct id)", message.from_user.id)
        except Exception as e:
            logger.exception("Error resolving input '%s': %s", message.text, e)

        if not pkg:
            await message.answer(
                "Couldn't find the specified movie. Check your spelling or try pasting the IMDB id or a link like tt0903624."
            )
            return

        # Send movie info with poster/caption
        try:
            caption, image = make_movie_reply(pkg)
            if isinstance(image, (bytes, bytearray)):
                photo = BufferedInputFile(image, filename="poster.jpg")
                await message.answer_photo(photo=photo, caption=caption)
            else:
                try:
                    path = getattr(image, "name", None)
                    if path:
                        await message.answer_photo(photo=FSInputFile(path), caption=caption)
                    else:
                        await message.answer(caption)
                except Exception:
                    await message.answer(caption)
        except Exception as e:
            logger.warning("Failed to send movie poster, sending text only: %s", e)
            await message.answer(caption if "caption" in locals() else "Movie info not available.")
        # Store pkg for later flow and check if already in Plex library or torrents DB
        await state.update_data(pkg=pkg)
        # Plex presence
        try:
            in_plex = await asyncio.wait_for(
                asyncio.to_thread(plex_has_movie_by_imdb, int(pkg["imdb"])),
                timeout=10
            )
        except Exception as e:
            logger.debug("Plex presence check failed for imdb %s: %s", pkg.get("imdb"), e)
            in_plex = False
        # Torrents DB presence (existing or in-progress)
        in_torrents = False
        try:
            torrs = await asyncio.wait_for(
                asyncio.to_thread(check_one_against_torrents_by_imdb, int(pkg["imdb"])),
                timeout=10
            )
            if torrs:
                # Consider existing if any entry is not 'removed'
                in_torrents = any(t.get("status") in ["seeding", "downloading", "requested download"] for t in torrs)
        except Exception as e:
            logger.debug("Torrents DB check failed for imdb %s: %s", pkg.get("imdb"), e)
            in_torrents = False

        if in_plex or in_torrents:
            kb = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="Yes")], [KeyboardButton(text="No")]],
                resize_keyboard=True,
                one_time_keyboard=True,
            )
            note = "already in Plex" if in_plex else "already present in torrents (requested/downloading/seeding)"
            await message.answer(
                f"This title is {note}. Do you still want to download it again?",
                reply_markup=kb
            )
            await state.update_data(imdb_id=pkg.get("imdb"), origin="direct")
            await state.set_state(DownloadStates.confirm_redownload)
            return

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
            # Prompt to add to watchlist
            await state.update_data(imdb_id=pkg.get("imdb"))
            kb = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="Yes")],[KeyboardButton(text="No")]],
                resize_keyboard=True,
                one_time_keyboard=True,
            )
            await message.answer(
                "We couldn't find any torrents for this title right now.\nAdd this movie to your watchlist?",
                reply_markup=kb
            )
            await state.set_state(DownloadStates.deciding_watchlist)
            return

        # Build inline keyboard and present choices
        keyboard_schema = build_torrents_keyboard(torrents)
        inline_keyboard = []
        for row in keyboard_schema:
            inline_keyboard.append([
                InlineKeyboardButton(text=btn["text"], callback_data=btn["callback_data"]) for btn in row
            ])
        markup = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

        await message.answer("Please select one of the torrents", reply_markup=markup)
        await state.update_data(torrents=torrents)
        await state.set_state(DownloadStates.choosing_torrent)
        return

    # Title flow: search candidates and start Yes/No/Exit loop
    movies = None
    try:
        movies = await asyncio.wait_for(
            asyncio.to_thread(search_imdb_title, title_text),
            timeout=20
        )
    except asyncio.TimeoutError:
        logger.warning("Timeout while searching IMDB for '%s' (user=%s)", title_text, message.from_user.id)
    except Exception as e:
        logger.exception("Error during IMDB search for '%s': %s", title_text, e)

    if not movies or isinstance(movies, str):
        await message.answer(
            "Couldn't find any matching movies. Try refining your title or paste an IMDB link like https://www.imdb.com/title/tt0133093/."
        )
        await state.clear()
        return

    candidate_ids = [str(c.get("id")) for c in movies if isinstance(c, dict) and c.get("id")]
    if not candidate_ids:
        await message.answer("No usable candidates returned by IMDB. Please try another query.")
        await state.clear()
        return

    await state.update_data(candidates=candidate_ids, cand_idx=0, user_id=message.from_user.id)
    await state.set_state(DownloadStates.choosing_title)
    await _present_current_candidate(message, state)


async def _present_current_candidate(message: Message, state: FSMContext):
    """
    Present the current candidate (by cand_idx) with poster and Yes/No/Exit inline buttons.
    Skips invalid/unresolvable candidates automatically.
    """
    data = await state.get_data()
    candidates: List[str] = data.get("candidates", [])
    idx: int = int(data.get("cand_idx", 0))
    user_id: int = int(data.get("user_id", 0))

    # Bounds check
    if idx >= len(candidates):
        await message.answer("No other matches were found. Please try another search.")
        await state.clear()
        return

    imdb_id = candidates[idx]
    pkg = None
    try:
        pkg = await asyncio.wait_for(
            asyncio.to_thread(get_pkg_for_input, imdb_id, user_id),
            timeout=20
        )
    except asyncio.TimeoutError:
        logger.warning("Timeout while resolving pkg for candidate imdb %s (user=%s)", imdb_id, user_id)
    except Exception as e:
        logger.exception("Error resolving candidate imdb %s: %s", imdb_id, e)

    if not pkg:
        # Move to next candidate
        await state.update_data(cand_idx=idx + 1)
        return await _present_current_candidate(message, state)

    # Build Yes/No/Exit keyboard
    ynx_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Yes", callback_data="CAND:YES"),
                InlineKeyboardButton(text="No", callback_data="CAND:NO"),
                InlineKeyboardButton(text="Exit", callback_data="CAND:EXIT"),
            ]
        ]
    )

    # Send poster/caption for this candidate
    try:
        caption, image = make_movie_reply(pkg)
        if isinstance(image, (bytes, bytearray)):
            photo = BufferedInputFile(image, filename="poster.jpg")
            await message.answer_photo(photo=photo, caption=caption, reply_markup=ynx_keyboard)
        else:
            try:
                path = getattr(image, "name", None)
                if path:
                    await message.answer_photo(photo=FSInputFile(path), caption=caption, reply_markup=ynx_keyboard)
                else:
                    await message.answer(caption, reply_markup=ynx_keyboard)
            except Exception:
                await message.answer(caption, reply_markup=ynx_keyboard)
    except Exception as e:
        logger.warning("Failed to send movie poster for candidate %s, text only: %s", imdb_id, e)
        await message.answer("Is this your movie?", reply_markup=ynx_keyboard)


@router.callback_query(F.data == "CAND:YES", DownloadStates.choosing_title)
async def accept_candidate(callback: CallbackQuery, state: FSMContext):
    """
    User accepted the current candidate -> fetch torrents and move to choosing_torrent.
    """
    await callback.answer()
    data = await state.get_data()
    candidates: List[str] = data.get("candidates", [])
    idx: int = int(data.get("cand_idx", 0))

    if idx >= len(candidates):
        await callback.message.answer("No candidate available. Please start over.")
        await state.clear()
        return

    imdb_id = candidates[idx]
    # Before fetching torrents, check presence in Plex or torrents DB and prompt if already present
    try:
        in_plex = await asyncio.wait_for(
            asyncio.to_thread(plex_has_movie_by_imdb, int(imdb_id)),
            timeout=10
        )
    except Exception as e:
        logger.debug("Plex presence check failed for imdb %s: %s", imdb_id, e)
        in_plex = False
    in_torrents = False
    try:
        torrs = await asyncio.wait_for(
            asyncio.to_thread(check_one_against_torrents_by_imdb, int(imdb_id)),
            timeout=10
        )
        if torrs:
            in_torrents = any(t.get("status") in ["seeding", "downloading", "requested download"] for t in torrs)
    except Exception as e:
        logger.debug("Torrents DB check failed for imdb %s: %s", imdb_id, e)
        in_torrents = False

    if in_plex or in_torrents:
        kb = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Yes")], [KeyboardButton(text="No")]],
            resize_keyboard=True,
            one_time_keyboard=True,
        )
        note = "already in Plex" if in_plex else "already present in torrents (requested/downloading/seeding)"
        await callback.message.answer(
            f"This title is {note}. Do you still want to download it again?",
            reply_markup=kb
        )
        await state.update_data(imdb_id=int(imdb_id), origin="candidate")
        await state.set_state(DownloadStates.confirm_redownload)
        return

    torrents: List[Dict[str, Any]] = []
    try:
        torrents = await asyncio.wait_for(
            asyncio.to_thread(get_torrents_for_imdb_id, imdb_id),
            timeout=20
        ) or []
        torrents = sorted(torrents, key=lambda k: k.get("size", 0))
    except asyncio.TimeoutError:
        logger.warning("Timeout while fetching torrents for imdb %s", imdb_id)
    except Exception as e:
        logger.exception("Error fetching torrents for imdb %s: %s", imdb_id, e)

    if not torrents:
        # Prompt to add to watchlist
        await state.update_data(imdb_id=int(imdb_id))
        kb = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Yes")],[KeyboardButton(text="No")]],
            resize_keyboard=True,
            one_time_keyboard=True,
        )
        await callback.message.answer(
            "We couldn't find any torrents for this title right now.\nAdd this movie to your watchlist?",
            reply_markup=kb
        )
        await state.set_state(DownloadStates.deciding_watchlist)
        return

    # Build inline keyboard and present choices
    keyboard_schema = build_torrents_keyboard(torrents)
    inline_keyboard = []
    for row in keyboard_schema:
        inline_keyboard.append([
            InlineKeyboardButton(text=btn["text"], callback_data=btn["callback_data"]) for btn in row
        ])
    markup = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

    await callback.message.answer("Please select one of the torrents", reply_markup=markup)
    await state.update_data(torrents=torrents)
    await state.set_state(DownloadStates.choosing_torrent)


@router.callback_query(F.data == "CAND:NO", DownloadStates.choosing_title)
async def reject_candidate(callback: CallbackQuery, state: FSMContext):
    """
    User rejected current candidate -> move to next candidate or finish.
    """
    await callback.answer()
    data = await state.get_data()
    idx: int = int(data.get("cand_idx", 0))
    await state.update_data(cand_idx=idx + 1)
    await _present_current_candidate(callback.message, state)


@router.callback_query(F.data == "CAND:EXIT", DownloadStates.choosing_title)
async def exit_candidates(callback: CallbackQuery, state: FSMContext):
    """
    User exited the candidate loop.
    """
    await callback.answer()
    await state.clear()
    await callback.message.answer("Cancelled. You can try another search from the main menu.")


@router.callback_query(F.data.startswith("TORR:"), DownloadStates.choosing_torrent)
async def torrent_selection(callback: CallbackQuery, state: FSMContext):
    """
    Handle the torrent selection; send to Transmission and update DB.
    """
    await callback.answer()
    data = await state.get_data()
    torrents = data.get("torrents", [])
    try:
        torr_id_str = callback.data.split(":", 1)[1]
        torr_id = int(torr_id_str)
    except Exception:
        torr_id = 0

    success, msg = perform_download(torr_id, torrents, callback.from_user.id)
    # Edit the selection message with the result to keep chat tidy
    try:
        await callback.message.edit_text(msg)
    except Exception:
        await callback.message.answer(msg)

    await state.clear()

# Handlers for watchlist quick actions sent by background WatchlistService
from typing import Optional

@router.message(F.text.regexp(r"^/WatchMatch_\d+$"))
async def handle_watchmatch_command(message: Message, state: FSMContext):
    """
    Triggered by messages like '/WatchMatch_123456'.
    Resolves the movie, shows info, fetches torrents and moves user into the choosing_torrent state.
    Mirrors the direct-id branch in handle_movie_query for consistency.
    """
    # imdb numeric id (strip prefix)
    try:
        imdb_id_text = message.text.split("_", 1)[1]
        imdb_id_text = "".join(ch for ch in imdb_id_text if ch.isdigit())
    except Exception:
        await message.answer("Invalid command format.")
        return

    await message.answer("Just a sec until we get data about this title...")

    # Resolve pkg
    pkg: Optional[Dict[str, Any]] = None
    try:
        pkg = await asyncio.wait_for(
            asyncio.to_thread(get_pkg_for_input, imdb_id_text, message.from_user.id),
            timeout=20
        )
    except asyncio.TimeoutError:
        logger.warning("Timeout while resolving input for /WatchMatch (user=%s)", message.from_user.id)
    except Exception as e:
        logger.exception("Error resolving input for /WatchMatch '%s': %s", imdb_id_text, e)

    if not pkg:
        await message.answer("Couldn't find the specified movie. Try again later.")
        return

    # Send movie info with poster/caption
    try:
        caption, image = make_movie_reply(pkg)
        if isinstance(image, (bytes, bytearray)):
            photo = BufferedInputFile(image, filename="poster.jpg")
            await message.answer_photo(photo=photo, caption=caption)
        else:
            try:
                path = getattr(image, "name", None)
                if path:
                    await message.answer_photo(photo=FSInputFile(path), caption=caption)
                else:
                    await message.answer(caption)
            except Exception:
                await message.answer(caption)
    except Exception as e:
        logger.warning("Failed to send movie poster for /WatchMatch, sending text only: %s", e)
        await message.answer("Movie info not available.")

    # Fetch torrents
    torrents: List[Dict[str, Any]] = []
    try:
        torrents = await asyncio.wait_for(
            asyncio.to_thread(get_torrents_for_imdb_id, pkg["imdb"]),
            timeout=20
        ) or []
        torrents = sorted(torrents, key=lambda k: k.get("size", 0))
    except asyncio.TimeoutError:
        logger.warning("Timeout while fetching torrents for imdb %s (/WatchMatch)", pkg.get("imdb"))
    except Exception as e:
        logger.exception("Error fetching torrents for imdb %s (/WatchMatch): %s", pkg.get("imdb"), e)

    if not torrents:
        await message.answer("We couldn't find any torrents for this title right now.")
        await state.clear()
        return

    # Build inline keyboard and present choices
    keyboard_schema = build_torrents_keyboard(torrents)
    inline_keyboard = []
    for row in keyboard_schema:
        inline_keyboard.append([
            InlineKeyboardButton(text=btn["text"], callback_data=btn["callback_data"]) for btn in row
        ])
    markup = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

    await message.answer("Please select one of the torrents", reply_markup=markup)
    await state.update_data(torrents=torrents)
    await state.set_state(DownloadStates.choosing_torrent)


@router.message(F.text.regexp(r"^/UnWatchMatch_\d+$"))
async def handle_unwatchmatch_command(message: Message):
    """
    Triggered by messages like '/UnWatchMatch_123456'.
    Marks the watchlist item as closed so no further alerts will be sent for this movie.
    """
    try:
        imdb_id_text = message.text.split("_", 1)[1]
        imdb_id = int("".join(ch for ch in imdb_id_text if ch.isdigit()))
    except Exception:
        await message.answer("Invalid command format.")
        return

    # Local import to avoid additional top-level dependency change
    try:
        from services.watchlist_service import update_watchlist_item_status  # noqa
    except Exception as e:
        logger.exception("Unable to load update_watchlist_item_status: %s", e)
        await message.answer("Internal error while updating your watchlist preference.")
        return

    try:
        update_watchlist_item_status(imdb_id, message.from_user.id, "closed")
        await message.answer("Done, no more watchlist updates for this movie.")
    except Exception as e:
        logger.exception("Failed to update watchlist status for imdb %s: %s", imdb_id, e)
        await message.answer("Could not update your watchlist preferences right now.")

# Handler for confirming re-download when title is already in Plex
@router.message(DownloadStates.confirm_redownload)
async def confirm_redownload_handler(message: Message, state: FSMContext):
    txt = (message.text or "").strip().lower()
    data = await state.get_data()
    imdb_id = data.get("imdb_id")
    origin = data.get("origin")  # 'direct' or 'candidate'

    if txt not in ("yes", "no"):
        await message.answer("Please answer Yes or No.")
        return

    if txt == "no":
        await message.answer("Okay, we won't download it again.")
        await state.clear()
        return

    # Proceed to fetch torrents and continue the normal flow
    torrents: List[Dict[str, Any]] = []
    try:
        torrents = await asyncio.wait_for(
            asyncio.to_thread(get_torrents_for_imdb_id, imdb_id),
            timeout=20
        ) or []
        torrents = sorted(torrents, key=lambda k: k.get("size", 0))
    except asyncio.TimeoutError:
        logger.warning("Timeout while fetching torrents for imdb %s (confirm_redownload)", imdb_id)
    except Exception as e:
        logger.exception("Error fetching torrents for imdb %s (confirm_redownload): %s", imdb_id, e)

    if not torrents:
        # Prompt to add to watchlist reusing same flow
        await state.update_data(imdb_id=int(imdb_id))
        kb = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Yes")], [KeyboardButton(text="No")]],
            resize_keyboard=True,
            one_time_keyboard=True,
        )
        await message.answer(
            "We couldn't find any torrents for this title right now.\nAdd this movie to your watchlist?",
            reply_markup=kb
        )
        await state.set_state(DownloadStates.deciding_watchlist)
        return

    # Build inline keyboard and present choices
    keyboard_schema = build_torrents_keyboard(torrents)
    inline_keyboard = []
    for row in keyboard_schema:
        inline_keyboard.append([
            InlineKeyboardButton(text=btn["text"], callback_data=btn["callback_data"]) for btn in row
        ])
    markup = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

    await message.answer("Please select one of the torrents", reply_markup=markup)
    await state.update_data(torrents=torrents)
    await state.set_state(DownloadStates.choosing_torrent)


# Handlers for deciding whether to add a movie to watchlist when no torrents are found
@router.message(DownloadStates.deciding_watchlist)
async def decide_add_to_watchlist(message: Message, state: FSMContext):
    """
    Handles Yes/No decision after prompting to add movie to watchlist when no torrents are found.
    """
    txt = (message.text or "").strip().lower()
    data = await state.get_data()
    imdb_id_val = data.get("imdb_id")

    # Normalize to numeric imdb id
    try:
        imdb_numeric = int("".join([c for c in str(imdb_id_val) if str(c).isdigit()]))
    except Exception:
        imdb_numeric = None

    if txt == "yes" and imdb_numeric:
        # Ensure user exists in DB and retrieve
        try:
            ensure_user_exists(message.from_user.id, message.from_user.full_name)
        except Exception:
            pass
        try:
            user = get_user_by_tgram_id(message.from_user.id)
        except Exception:
            user = {"telegram_chat_id": message.from_user.id, "imdb_id": None}
        try:
            add_to_watchlist(deconvert_imdb_id(imdb_numeric), user, "new")
            await message.answer("Added to watchlist!")
        except Exception as e:
            logger.exception("Failed to add imdb %s to watchlist for user %s: %s", imdb_numeric, message.from_user.id, e)
            await message.answer("Could not add to watchlist right now.")
        await state.clear()
        return

    if txt == "no":
        await message.answer("Okay, not added to your watchlist.")
        await state.clear()
        return

    # Fallback for unexpected input
    await message.answer("Please answer Yes or No.")