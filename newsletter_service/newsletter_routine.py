import os
from datetime import datetime, date

import requests
from apscheduler.schedulers.blocking import BlockingScheduler

from email_tools import do_email
from utils import torr_cypher, get_movie_details, setup_logger, timing, check_against_my_torrents, \
    check_database, parse_torr_name

TZ = os.getenv('TZ')
API_URL = os.getenv('API_URL')
USER = os.getenv('FL_USER')
PASSKEY = os.getenv('PASSKEY')
MOVIE_HDRO = os.getenv('MOVIE_HDRO')
MOVIE_4K = os.getenv('MOVIE_4K')
NEWSLETTER_ROUTINE_TIMES = os.getenv('NEWSLETTER_ROUTINE_TIMES')
NEWSLETTER_ROUTINE_TIMES = NEWSLETTER_ROUTINE_TIMES.split(',')

logger = setup_logger("FilelistRoutine")

# Torrent API availability check helpers
def _resolve_torr_api_base():
    path = os.getenv('TORR_API_PATH') or '/torr-api'
    base = path.strip('/')
    return base or 'torr-api'

def torr_api_is_available(timeout=3):
    """
    Returns True if TORR API health endpoint responds 200 OK.
    Treats 403/503 and any exception as unavailable.
    """
    host = os.getenv('TORR_API_HOST') or '127.0.0.1'
    port = os.getenv('TORR_API_PORT') or '9092'
    base = _resolve_torr_api_base()
    url = f"http://{host}:{port}/{base}/health"
    try:
        r = requests.get(url, timeout=timeout)
        if r.status_code == 200:
            return True
        if r.status_code in (403, 503):
            logger.info(f"TORR API health check returned {r.status_code}; treating as unavailable")
            return False
        logger.info(f"TORR API health check returned {r.status_code}; treating as unavailable")
        return False
    except Exception as e:
        logger.warning(f"TORR API health check error: {e}")
        return False

# https://filelist.io/forums.php?action=viewtopic&topicid=120435

def check_in_my_torrents(torrents):
    new_torrents = []
    already_in_db = check_against_my_torrents(torrents)
    already_in_db = [x['torr_id'] for x in already_in_db] if already_in_db else []
    for torrent in torrents:
        if torrent['id'] not in already_in_db:
            new_torrents.append(torrent)
    return new_torrents


def retrieve_bulk_from_dbs(items):
    logger.info("Getting IMDB TMDB and OMDB metadata...")
    return [get_movie_details(item) for item in items]


def get_latest_torrents(n=100, category=MOVIE_HDRO):
    """
    returns last n movies from filelist API.
    n default 100
    movie category default HD RO
    """
    logger.info('Getting RSS feeds')
    r = requests.get(
        url=API_URL,
        params={
            'username': USER,
            'passkey': PASSKEY,
            'action': 'latest-torrents',
            'category': category,
            'limit': n,
        },
    )
    if category == MOVIE_4K:
        torrents = [x for x in r.json() if 'Remux' in x['name']]
    else:
        torrents = r.json()

    # Only keep movies from last 2 years
    # TODO this should be configurable
    torrents_parsed = []
    for torrent in torrents:
        parsed = parse_torr_name(torrent['name'])
        if parsed and parsed.get('year', 1999) in [date.today().year, date.today().year - 1]:
            torrent.update(parsed)
            torrents_parsed.append(torrent)
    logger.info(f"Got {len(torrents)} new torrents")
    return torrents


@timing
def feed_routine(cypher=torr_cypher):
    # Pre-check Torrent API availability to avoid sending broken newsletter
    if not torr_api_is_available(timeout=3):
        logger.warning("Torrent service not accessible right now; skipping newsletter run")
        return

    # fetch latest movies
    new_movies = get_latest_torrents()

    # filter out those already in database with same or better quality and mark
    # the rest if they are already in db
    new_movies = check_in_my_torrents(new_movies)

    # get IMDB, TMDB and OMDB data for these new movies.
    new_movies = retrieve_bulk_from_dbs(new_movies)
    new_movies = [x for x in new_movies if x]

    # send to user to choose
    do_email(new_movies)


def info_jobs():
    jobs = scheduler.get_jobs()
    logger.info(f"Found {len(jobs)} in this scheduler.")
    for job in scheduler.get_jobs():
        message = f"Job {job.name} with the general trigger {job.trigger}"
        if job.pending:
            message += f" is yet to be added to the jobstore, no next run time yet."
        else:
            message += f" will run next on {job.next_run_time}"
        logger.info(message)


if __name__ == '__main__':
    check_database()
    feed_routine()

    scheduler = BlockingScheduler(timezone=TZ)

    for hour in NEWSLETTER_ROUTINE_TIMES:

        scheduler.add_job(feed_routine, 'cron', hour=int(hour), id=f"Filelist Routine {hour} o'clock",
                          coalesce=True, misfire_grace_time=3000000, replace_existing=True)

    scheduler.add_job(info_jobs, 'interval', minutes=30, id='Filelist RoutineInfo', coalesce=True,
                      next_run_time=datetime.now(), misfire_grace_time=3000000, replace_existing=True)

    scheduler.start()
