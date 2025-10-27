import logging
from typing import Dict, List

from utils import make_client, get_requested_torrents_for_tgram_user, get_torr_name

logger = logging.getLogger("ProgressService")


def get_progress_rows(user_id: int) -> List[Dict[str, str]]:
    """
    Return progress rows for torrents requested by the given user.

    Each row contains:
    - TorrentName
    - Resolution
    - Status
    - Progress
    - ETA
    """
    torrents = get_requested_torrents_for_tgram_user(user_id) or []
    if not torrents:
        return []

    # Filter out removed and email-notified entries (legacy behavior)
    torrents = list(reversed([x for x in torrents if x.get("status") not in ["removed", "user notified (email)"]]))

    # Transmission client and torrent maps
    try:
        client = make_client()
        client_torrents_raw = client.get_torrents()
        client_torrents = {x.hashString: x for x in client_torrents_raw}
        client_torrents_names = {x.hashString: x.name for x in client_torrents_raw}
    except Exception as e:
        logger.warning("Failed to fetch torrents from Transmission client: %s", e)
        client_torrents = {}
        client_torrents_names = {}

    # Enrich with progress data
    for t in torrents:
        status = t.get("status")
        hash_str = t.get("torr_hash")
        t["progress"] = "Unknown"
        t["date_started"] = "Unknown"
        t["eta"] = "Unknown"

        if status == "seeding":
            t["progress"] = "100%"
            t["date_started"] = None
            t["eta"] = "Finished"
            continue

        if hash_str and hash_str in client_torrents:
            torr_resp = client_torrents.get(hash_str)
            try:
                left = torr_resp.left_until_done
                total = torr_resp.total_size or 1
                pct = max(0.0, 100.0 - ((left / total) * 100.0))
                t["progress"] = f"{pct:.2f}%"
                t["date_started"] = getattr(torr_resp, "date_started", "Unknown")
                eta_obj = getattr(torr_resp, "eta", None)
                if hasattr(eta_obj, "seconds"):
                    t["eta"] = f"{int(eta_obj.seconds // 60)} minutes"
                else:
                    t["eta"] = "Unknown"
            except Exception as e:
                logger.warning("Error obtaining progress/ETA for hash %s: %s", hash_str, e)

    # Build rows
    rows: List[Dict[str, str]] = []
    for t in torrents:
        hash_str = t.get("torr_hash")
        name = client_torrents_names.get(hash_str)
        safe_name = get_torr_name(name) if name else None
        rows.append(
            {
                "TorrentName": safe_name,
                "Resolution": t.get("resolution"),
                "Status": t.get("status"),
                "Progress": t.get("progress"),
                "ETA": t.get("eta"),
            }
        )
    return rows