from settings import REVIEW_INTERVAL_REFRESH, OMDB_API_LIMIT
from utils import logger, connect_mysql, close_mysql, update_many, convert_imdb_id
from tmdb_omdb_tools import TMDB
import datetime


def get_omdb_data():
    """
    populates the database with data from TMDB
    Extra keys:
    Poze, Country, Lang, Ovrw(short descr), score, trailer_link,
    :return:
    """
    # New titles
    logger.info("Downloading data for new TMDB titles")
    tmdb_inserted = 0
    conn, new_for_tmdb_cursor = get_new_imdb_titles('tmdb_data')
    if new_for_tmdb_cursor:
        while new_for_tmdb_cursor.with_rows:
            batch = new_for_tmdb_cursor.fetchmany(OMDB_API_LIMIT)
            batch = [process_new_omdb(item['tconst']) for item in batch]
            update_many(batch, 'tmdb_data')
            tmdb_inserted += 1
            logger.info(f"Inserted {tmdb_inserted * OMDB_API_LIMIT} into TMDB database")


def get_new_imdb_titles(target_table):
    conn, cursor = connect_mysql()
    q = f"SELECT tconst FROM title_basics WHERE  tconst NOT IN (SELECT imdb_id FROM {target_table})"
    cursor.execute(q)
    if cursor.with_rows:
        return conn, cursor
    else:
        return None, None


def process_new_omdb(id):
    tmdb = TMDB(convert_imdb_id(id), '', '')
    tmdb.get_data()
    return {
        'imdb_id': id,
        'country': tmdb.country,
        'lang': tmdb.lang,
        'ovrw': tmdb.ovrw,
        'score': tmdb.score,
        'trailer_link': tmdb.trailer,
        'last_update': datetime.datetime.now(),
    }


if __name__ == '__main__':
    get_omdb_data()