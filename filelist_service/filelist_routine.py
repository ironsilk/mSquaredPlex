import os
import time
import PTN
import requests

from utils import torr_cypher, get_movie_details, update_many, setup_logger, timing, check_against_my_torrents, \
    check_database, Torrent
from email_tools import send_email

API_URL = os.getenv('API_URL')
USER = os.getenv('USER')
PASSKEY = os.getenv('PASSKEY')
MOVIE_HDRO = os.getenv('MOVIE_HDRO')
MOVIE_4K = os.getenv('MOVIE_4K')
FLIST_ROUTINE_SLEEP_TIME = int(os.getenv('FLIST_ROUTINE_SLEEP_TIME'))


logger = setup_logger("FilelistRoutine")


# https://filelist.io/forums.php?action=viewtopic&topicid=120435

def check_in_my_torrents(torrents):
    already_in_db = check_against_my_torrents(torrents)
    if not already_in_db:
        already_in_db = []
    for torrent in torrents:
        if torrent['id'] in already_in_db:
            torrent['torr_already_processed'] = True
        else:
            torrent['torr_already_processed'] = False
    return torrents


def retrieve_bulk_from_dbs(items):
    logger.info("Getting IMDB TMDB and OMDB metadata...")
    return [get_movie_details(item) for item in items]


def update_my_torrents_db(items):
    items = [{'torr_id': x['id'],
              'imdb_id': x['imdb_id'],
              'status': 'users notified',
              'resolution': int(PTN.parse(x['name'])['resolution'][:-1]),
              }
             for x in items]
    update_many(items, Torrent, Torrent.torr_id)


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
        return [x for x in r.json() if 'Remux' in x['name']]
    logger.info(f"Got {len(r.json())} new torrents")
    return r.json()


def filter_results(new_movies):
    logger.info("Filtering results...")
    # Check against my_torrents_database
    filtered = check_in_my_torrents(new_movies)
    # Remove already seen torrents - can be removed for testing purposes
    print(filtered)
    filtered = [x for x in filtered if not x['torr_already_processed']]

    return filtered


@timing
def feed_routine(cypher):
    # fetch latest movies
    new_movies = get_latest_torrents()

    # filter out those already in database with same or better quality and mark
    # the rest if they are already in db
    new_movies = filter_results(new_movies)

    # get IMDB, TMDB and OMDB data for these new movies.
    new_movies = retrieve_bulk_from_dbs(new_movies)

    # send to user to choose
    send_email(new_movies, cypher)

    # update torrents in my_torrents db
    update_my_torrents_db(new_movies)


def run_forever(cypher=torr_cypher, sleep_time=60*60*FLIST_ROUTINE_SLEEP_TIME):
    """
    Run routine - run time is negligible, will sleep for full time provided in settings.
    :param cypher: AES cypher for torrent API hashes
    :param sleep_time: default at 12 hrs
    :return: happiness
    """
    while True:
        feed_routine(cypher)
        logger.info(f"Finished routine, sleeping for {FLIST_ROUTINE_SLEEP_TIME} hours")
        time.sleep(sleep_time)


if __name__ == '__main__':
    check_database()
    run_forever()
