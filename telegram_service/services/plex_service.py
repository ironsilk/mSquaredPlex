import logging
from typing import Optional

from utils import connect_plex

logger = logging.getLogger("PlexService")


def _extract_imdb_numeric_from_guid(guid: str) -> Optional[str]:
    """
    Extract numeric imdb id from a Plex GUID string like:
    'com.plexapp.agents.imdb://tt0133093?lang=en'
    """
    if not guid or "imdb" not in guid:
        return None
    try:
        part = guid.split("//tt", 1)[-1]
        digits = "".join(ch for ch in part if ch.isdigit())
        return digits or None
    except Exception:
        return None


def plex_has_movie_by_imdb(imdb_numeric_id: int) -> bool:
    """
    Return True if a movie with the given imdb numeric id exists in the Plex Movies library.
    Relies on utils.connect_plex() configuration (PLEX_HOST/PLEX_TOKEN/etc).
    """
    try:
        account, plex = connect_plex()
    except Exception as e:
        logger.debug("connect_plex failed: %s", e)
        return False

    try:
        section = plex.library.section("Movies")
    except Exception as e:
        logger.debug("Could not access Plex 'Movies' section: %s", e)
        return False

    try:
        for item in section.all():
            try:
                for g in (item.guids or []):
                    digits = _extract_imdb_numeric_from_guid(getattr(g, "id", "") or "")
                    if digits and digits == str(imdb_numeric_id):
                        return True
            except Exception:
                continue
    except Exception as e:
        logger.debug("Error iterating Plex library: %s", e)
        return False

    return False