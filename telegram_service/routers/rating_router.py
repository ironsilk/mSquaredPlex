import logging
import asyncio
import datetime
from typing import List, Dict, Any

from aiogram import Router, F
from aiogram.types import (
    Message,
    BufferedInputFile,
    FSInputFile,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from bot_utils import make_movie_reply, search_imdb_title
from services.download_service import get_pkg_for_input, parse_imdb_input
from utils import (
    get_movies_for_bulk_rating,
    update_many,
    Movie,
    get_my_movie_by_imdb,
    convert_imdb_id,
)

router = Router()
logger = logging.getLogger("RatingRouter")


class RatingStates(StatesGroup):
    choosing_mode = State()
    awaiting_query = State()
    choosing_title = State()
    submitting_rating = State()
    bulk_submitting = State()


def rate_mode_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="New title"), KeyboardButton(text="Rate seen movies")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def rating_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="1"), KeyboardButton(text="2")],
            [KeyboardButton(text="3"), KeyboardButton(text="4")],
            [KeyboardButton(text="5"), KeyboardButton(text="6")],
            [KeyboardButton(text="7"), KeyboardButton(text="8")],
            [KeyboardButton(text="9"), KeyboardButton(text="10")],
            [KeyboardButton(text="I've changed my mind")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def rating_keyboard_bulk() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="1"), KeyboardButton(text="2")],
            [KeyboardButton(text="3"), KeyboardButton(text="4")],
            [KeyboardButton(text="5"), KeyboardButton(text="6")],
            [KeyboardButton(text="7"), KeyboardButton(text="8")],
            [KeyboardButton(text="9"), KeyboardButton(text="10")],
            [KeyboardButton(text="Skip this movie.")],
            [KeyboardButton(text="Exit rating process.")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


@router.message(F.text == "🌡️ Rate a title")
async def rate_entry(message: Message, state: FSMContext):
    """
    Ask the user to choose between rating a new title or rating seen-but-unrated movies.
    """
    await state.set_state(RatingStates.choosing_mode)
    await message.answer(
        "Do you wish to rate a new title or seen-but-unrated movies?",
        reply_markup=rate_mode_keyboard(),
    )


@router.message(RatingStates.choosing_mode)
async def rate_choose_mode(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if text == "New title":
        await state.set_state(RatingStates.awaiting_query)
        await message.answer(
            "Great, send an IMDB id (e.g. tt0903624), a title, or an IMDB link.\n"
            "Example inputs:\n"
            "- tt0903624\n"
            "- The Matrix\n"
            "- https://www.imdb.com/title/tt0133093/"
        )
        return

    if text == "Rate seen movies":
        await message.answer("Preparing movies...")
        try:
            unrated: List[Dict[str, Any]] = await asyncio.wait_for(
                asyncio.to_thread(get_movies_for_bulk_rating, message.from_user.id),
                timeout=20
            ) or []
        except asyncio.TimeoutError:
            logger.warning("Timeout retrieving unrated movies for user %s", message.from_user.id)
            await message.answer("Timed out while preparing unrated movies. Please try again.")
            await state.clear()
            return
        except Exception as e:
            logger.exception("Error retrieving unrated movies for user %s: %s", message.from_user.id, e)
            await message.answer("Error while preparing unrated movies.")
            await state.clear()
            return

        if not unrated:
            await message.answer("You have no unrated movies!")
            await state.clear()
            return

        await state.update_data(unrated_queue=unrated)
        await _rate_next_in_bulk(message, state)
        return

    await message.answer("Please choose one of the options.")


@router.message(RatingStates.awaiting_query)
async def rate_handle_query(message: Message, state: FSMContext):
    """
    Resolve input to movie candidates and present Yes/No/Exit confirmation before rating.
    Mirrors the download flow's candidate loop.
    """
    await message.answer("Just a sec until we get data about this title...")
    imdb_id, title_text = parse_imdb_input(message.text)

    # If we have a direct imdb id/link, resolve single candidate and confirm
    if imdb_id:
        pkg = None
        try:
            pkg = await asyncio.wait_for(
                asyncio.to_thread(get_pkg_for_input, message.text, message.from_user.id),
                timeout=20
            )
        except asyncio.TimeoutError:
            logger.warning("Timeout while resolving rating input for user %s", message.from_user.id)
        except Exception as e:
            logger.exception("Error resolving input '%s': %s", message.text, e)

        if not pkg:
            await message.answer(
                "Couldn't find the specified movie. Check your spelling or try pasting the IMDB id or a link like tt0903624."
            )
            return

        # Store single candidate context and present Yes/No/Exit
        await state.update_data(candidates=[str(int(pkg["imdb"]))], cand_idx=0, user_id=message.from_user.id)
        await state.set_state(RatingStates.choosing_title)
        await _present_current_candidate_for_rating(message, state)
        return

    # Title flow: search IMDB and start candidate confirmation loop
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
    await state.set_state(RatingStates.choosing_title)
    await _present_current_candidate_for_rating(message, state)


@router.message(RatingStates.submitting_rating)
async def rate_submit_single(message: Message, state: FSMContext):
    """
    Handle rating submission for single-title rating.
    """
    data = await state.get_data()
    imdb_id = int(data.get("imdb"))
    user_id = message.from_user.id

    if message.text in [str(x) for x in range(1, 11)]:
        # Persist rating
        await _persist_rating(user_id, imdb_id, int(message.text), origin="simple", message=message)
        await state.clear()
        return

    if message.text == "I've changed my mind":
        # Mark refused
        await _mark_refused(user_id, imdb_id)
        await message.answer("Ok, no worries! I won't bother you about this title anymore.\nHave a great day!")
        await state.clear()
        return

    await message.answer("Please choose an option from the keyboard.")


@router.message(RatingStates.bulk_submitting)
async def rate_submit_bulk(message: Message, state: FSMContext):
    """
    Handle rating submission for bulk rating queue.
    """
    data = await state.get_data()
    imdb_id = int(data.get("imdb"))
    user_id = message.from_user.id

    if message.text in [str(x) for x in range(1, 11)]:
        await _persist_rating(user_id, imdb_id, int(message.text), origin="multiple", message=message)
        # Continue with next
        await _rate_next_in_bulk(message, state)
        return

    if message.text == "Skip this movie.":
        await _mark_refused(user_id, imdb_id)
        await message.answer("Skipped. Moving to next.")
        await _rate_next_in_bulk(message, state)
        return

    if message.text == "Exit rating process.":
        await message.answer("Ok, your progress is saved, come back anytime.")
        await state.clear()
        return

    await message.answer("Please choose an option from the keyboard.")


async def _rate_next_in_bulk(message: Message, state: FSMContext):
    """
    Pops next unrated movie and presents rating keyboard.
    """
    data = await state.get_data()
    queue: List[Dict[str, Any]] = data.get("unrated_queue", [])
    if not queue:
        await message.answer("No more movies left, good job!")
        await state.clear()
        return

    movie = queue.pop(0)
    await state.update_data(unrated_queue=queue)

    # Resolve and present movie info
    try:
        pkg = await asyncio.wait_for(
            asyncio.to_thread(get_pkg_for_input, str(movie.get("imdb_id", "")), message.from_user.id),
            timeout=20
        )
    except asyncio.TimeoutError:
        logger.warning("Timeout resolving pkg for imdb %s", movie.get("imdb_id"))
        return await _rate_next_in_bulk(message, state)
    except Exception as e:
        logger.exception("Error retrieving pkg for imdb %s: %s", movie.get("imdb_id"), e)
        return await _rate_next_in_bulk(message, state)

    if not pkg:
        return await _rate_next_in_bulk(message, state)

    await _send_movie_info_with_rating(message, pkg, single=False)
    await state.update_data(imdb=int(pkg["imdb"]), rate_origin="multiple")
    await state.set_state(RatingStates.bulk_submitting)


async def _send_movie_info_with_rating(message: Message, pkg: Dict[str, Any], single: bool):
    """
    Sends movie poster and caption, then presents rating keyboard.
    """
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
        await message.answer("Please choose a rating:")

    if single:
        await message.answer("Great, please choose a rating:", reply_markup=rating_keyboard())
    else:
        await message.answer("Please choose a rating", reply_markup=rating_keyboard_bulk())


async def _persist_rating(user_id: int, imdb_id: int, score: int, origin: str, message: Message):
    """
    Persist rating to DB and send IMDB link.
    Also set seen_date timestamp to align with legacy behavior.
    """
    item = get_my_movie_by_imdb(imdb_id, user_id)
    if item:
        item["rating_status"] = "rated in telegram"
        item["my_score"] = score
        item["seen_date"] = datetime.datetime.now()
    else:
        item = {
            "imdb_id": imdb_id,
            "my_score": score,
            "rating_status": "rated in telegram",
            "user_id": user_id,
            "seen_date": datetime.datetime.now(),
        }
    update_many([item], Movie, Movie.id)
    imdb_link = f"https://www.imdb.com/title/{convert_imdb_id(imdb_id)}/"
    await message.answer(
        f"Ok, great! Here's a link if you also want to rate it on IMDB:\n{imdb_link}",
        disable_web_page_preview=True,
    )


async def _mark_refused(user_id: int, imdb_id: int):
    item = get_my_movie_by_imdb(imdb_id, user_id)
    if item:
        item["rating_status"] = "refused to rate"
        update_many([item], Movie, Movie.id)
    else:
        item = {
            "imdb_id": imdb_id,
            "rating_status": "refused to rate",
            "user_id": user_id,
        }
        update_many([item], Movie, Movie.id)
# Candidate confirmation helpers for rating flow (Yes/No/Exit), mirroring download flow

async def _present_current_candidate_for_rating(message: Message, state: FSMContext):
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
        return await _present_current_candidate_for_rating(message, state)

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


@router.callback_query(F.data == "CAND:YES", RatingStates.choosing_title)
async def accept_candidate_for_rating(callback, state: FSMContext):
    """
    User accepted the current candidate -> present rating keyboard for that title.
    """
    await callback.answer()
    data = await state.get_data()
    candidates: List[str] = data.get("candidates", [])
    idx: int = int(data.get("cand_idx", 0))

    if idx >= len(candidates):
        await callback.message.answer("No candidate available. Please start over.")
        await state.clear()
        return

    imdb_id = int(candidates[idx])

    # Resolve pkg again to present info next to rating keyboard
    pkg = None
    try:
        pkg = await asyncio.wait_for(
            asyncio.to_thread(get_pkg_for_input, str(imdb_id), callback.from_user.id),
            timeout=20
        )
    except asyncio.TimeoutError:
        logger.warning("Timeout while resolving accepted candidate imdb %s", imdb_id)
    except Exception as e:
        logger.exception("Error resolving accepted candidate imdb %s: %s", imdb_id, e)

    await state.update_data(imdb=imdb_id, rate_origin="simple")
    if pkg:
        await _send_movie_info_with_rating(callback.message, pkg, single=True)
    else:
        await callback.message.answer("Great, please choose a rating:")

    await state.set_state(RatingStates.submitting_rating)


@router.callback_query(F.data == "CAND:NO", RatingStates.choosing_title)
async def reject_candidate_for_rating(callback, state: FSMContext):
    """
    User rejected current candidate -> move to next candidate or finish.
    """
    await callback.answer()
    data = await state.get_data()
    idx: int = int(data.get("cand_idx", 0))
    await state.update_data(cand_idx=idx + 1)
    await _present_current_candidate_for_rating(callback.message, state)


@router.callback_query(F.data == "CAND:EXIT", RatingStates.choosing_title)
async def exit_candidates_for_rating(callback, state: FSMContext):
    """
    User exited the candidate loop.
    """
    await callback.answer()
    await state.clear()
    await callback.message.answer("Cancelled. You can try another search from the main menu.")