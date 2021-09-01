import os
import time
import PTN
import requests

from utils import torr_cypher, connect_mysql, retrieve_one_from_dbs, update_many, setup_logger, timing, check_db
from email_tools import send_email

API_URL = os.getenv('API_URL')
USER = os.getenv('USER')
PASSKEY = os.getenv('PASSKEY')
MOVIE_HDRO = os.getenv('MOVIE_HDRO')
MOVIE_4K = os.getenv('MOVIE_4K')
FLIST_ROUTINE_SLEEP_TIME = int(os.getenv('FLIST_ROUTINE_SLEEP_TIME'))


logger = setup_logger("FilelistRoutine")


# https://filelist.io/forums.php?action=viewtopic&topicid=120435

def check_in_my_torrents(new_movies, cursor=None):
    if not cursor:
        conn, cursor = connect_mysql()
    q = "SELECT * FROM {table} WHERE torr_id IN ('{values}')".format(
        table='my_torrents',
        values="','".join([str(x['id']) for x in new_movies])
    )
    cursor.execute(q)
    already_in_db = [x['torr_id'] for x in cursor.fetchall()]
    for movie in new_movies:
        if movie['id'] in already_in_db:
            movie['torr_already_processed'] = True
        else:
            movie['torr_already_processed'] = False
    return new_movies


def retrieve_bulk_from_dbs(items):
    logger.info("Getting IMDB TMDB and OMDB metadata...")
    # Connections
    conn, cursor = connect_mysql(myimdb=True)
    return [retrieve_one_from_dbs(item, cursor) for item in items]


def update_my_torrents_db(items):
    items = [{'torr_id': x['id'],
              'imdb_id': x['imdb_id'],
              'status': 'users notified',
              'resolution': int(PTN.parse(x['name'])['resolution'][:-1]),
              }
             for x in items]
    update_many(items, 'my_torrents')


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
    filtered = [x for x in filtered if not x['torr_already_processed']]

    return filtered


@timing
def feed_routine(cypher):
    # fetch latest movies
    new_movies = get_latest_torrents(n=7)

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
    # TODO maybe make it run at a certain hour, 8AM 8 PM for example
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
    from dotenv import load_dotenv
    load_dotenv()
    check_db()
    run_forever()
