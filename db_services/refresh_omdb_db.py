import datetime
import time

from settings import REVIEW_INTERVAL_REFRESH, OMDB_API_LIMIT, INSERT_RATE
from tmdb_omdb_tools import OMDB
from utils import logger, connect_mysql, close_mysql, update_many, convert_imdb_id
from tmdb_omdb_tools import get_omdb


def get_omdb_data(session_not_found=[]):
    """
    populates the database with data from TMDB
    session_not_found are the IDs searched for and not found which can be passed to this function
    in order not to search for them again.
    Extra keys:
    Poze, Country, Lang, Ovrw(short descr), score, trailer_link,
    :return:
    """
    # New titles
    logger.info("Downloading data for new OMDB titles")
    # Get how many API calls we have left
    api_calls = get_omdb_api_limit()
    conn, new_for_omdb_cursor = get_new_imdb_titles('omdb_data', session_not_found)
    if new_for_omdb_cursor:
        while new_for_omdb_cursor.with_rows:
            if api_calls > INSERT_RATE:
                calls_to_make = INSERT_RATE
                stop = False
            else:
                calls_to_make = api_calls
                stop = True
            if calls_to_make < 0:
                calls_to_make = 0
            batch = new_for_omdb_cursor.fetchmany(calls_to_make)
            batch, session_not_found = process_items(batch, session_not_found)
            update_many(batch, 'omdb_data')
            logger.info(f"Inserted {calls_to_make} into OMDB database")
            api_calls -= calls_to_make
            if stop:
                # Sleep 1hr and repeat
                close_mysql(conn, new_for_omdb_cursor)
                logger.info('Sleeping for 1 hour.')
                time.sleep(360)
                get_omdb_data(session_not_found)
                break


def get_new_imdb_titles(target_table, session_not_found):
    values = ', '.join([str(x) for x in session_not_found])
    conn, cursor = connect_mysql()
    refresh_interval_date = datetime.datetime.now() - datetime.timedelta(days=REVIEW_INTERVAL_REFRESH)
    q = f"SELECT tconst FROM title_basics WHERE  tconst NOT IN (SELECT imdb_id FROM {target_table} " \
        f"WHERE last_update_omdb > '{str(refresh_interval_date)}')"
    if session_not_found:
        q = q + f" AND tconst NOT IN ({values})"
    cursor.execute(q)
    if cursor.with_rows:
        return conn, cursor
    else:
        return None, None


def get_omdb_api_limit():
    refresh_interval_date = datetime.datetime.now() - datetime.timedelta(days=1)
    conn, cursor = connect_mysql()
    q = f"SELECT imdb_id FROM  `omdb_data`" \
        f"WHERE last_update_omdb > '{str(refresh_interval_date)}'"
    cursor.execute(q)
    results = cursor.fetchall()
    return OMDB_API_LIMIT - len(results)


def process_items(items, session_not_found):
    new_items = []
    for item in items:
        item = get_omdb(item['tconst'])
        if not item['hit_omdb']:
            session_not_found.append(item['tconst'])
    return new_items, session_not_found


if __name__ == '__main__':
    get_omdb_data()
