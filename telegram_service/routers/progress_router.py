import asyncio
import logging
from aiogram import Router, F
from aiogram.types import Message

from services.progress_service import get_progress_rows

logger = logging.getLogger("ProgressRouter")
router = Router()


@router.message(F.text == "📊 Download progress")
async def show_download_progress(message: Message):
    """
    Show progress for all torrents requested by the current user.
    Uses services.progress_service.get_progress_rows() to gather data and formats a compact text summary.
    """
    user_id = message.from_user.id
    rows = []
    try:
        rows = await asyncio.wait_for(asyncio.to_thread(get_progress_rows, user_id), timeout=15)
    except asyncio.TimeoutError:
        await message.answer("Timed out while fetching progress. Please try again.")
        return
    except Exception as e:
        logger.exception("Error fetching progress for user %s: %s", user_id, e)
        await message.answer("Unexpected error while fetching progress.")
        return

    if not rows:
        await message.answer("No active or recent downloads.")
        return

    # Build a readable summary
    lines = []
    for r in rows:
        name = r.get("TorrentName") or "Movie"
        res = r.get("Resolution") or "N/A"
        status = r.get("Status") or "unknown"
        progress = r.get("Progress") or "Unknown"
        eta = r.get("ETA") or "Unknown"
        lines.append(f"{name} — {res}p — {status} — {progress} — ETA {eta}")

    msg = "Your downloads:\n" + "\n".join(lines)
    await message.answer(msg)