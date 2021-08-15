from imdb import IMDb
from imdb_dump_import import run_import
from settings import DUMPS_PATH, DB_URI, DUMPS_URL, REVIEW_INTERVAL_REFRESH, table_columns, INSERT_BATCH_SIZE
from utils import logger, connect_mysql, close_mysql, insert_sql, convert_imdb_id
from tmdb_omdb_tools import TMDB
import datetime
import requests
import lxml.html
import os
from tqdm import tqdm


def fetch_database_dumps():
    logger.info('Downloading dumps...')
    dom = lxml.html.fromstring(requests.get(DUMPS_URL).content)
    db_links = [x for x in dom.xpath('//a/@href') if '//' in x and 'interfaces' not in x]
    for url in db_links:
        name = url.split('/')[-1]
        logger.info('Downloading {x} dump'.format(x=name))
        response = requests.get(url, stream=True)

        with open(os.path.join(DUMPS_PATH, name), "wb") as handle:
            for data in tqdm(response.iter_content(chunk_size=1024)):
                handle.write(data)

    logger.info('Dumps ready.')


def update_imdb_db():
    # Download latest dumps
    fetch_database_dumps()
    # Update database with 'em
    run_import(DB_URI, DUMPS_PATH)


def get_extra_data():
    """
    populates the database with data from
    TMDB and OMDB
    Extra keys:
    TMDB: Poze, Country, Lang, Ovrw(short descr), score, trailer_link,
    OMDB: Awards, Country, Lang, meta_score, Rated, Rott_score, Score,
    :return:
    """
    # TMDB
    tmdb_inserted = 0
    conn, new_for_tmdb_cursor = get_new_imdb_titles('tmdb_data')
    if new_for_tmdb_cursor:
        while new_for_tmdb_cursor.with_rows:
            batch = new_for_tmdb_cursor.fetchmany(INSERT_BATCH_SIZE)
            batch = [process_new_tmdb(item['tconst']) for item in batch]
            insert_sql(batch, 'tmdb_data', list(table_columns['tmdb_data'].keys()))
            tmdb_inserted += 1
            logger.info(f"Inserted {tmdb_inserted * INSERT_BATCH_SIZE} into TMDB database")


def get_new_imdb_titles(target_table):
    conn, cursor = connect_mysql()
    q = f"SELECT tconst FROM title_basics WHERE  tconst NOT IN (SELECT imdb_id FROM {target_table})"

    """
    query original: trebuie tratate update-urile separat ca altfel o sa avem duplicate in baza.
    refresh_interval_date = datetime.datetime.now() - datetime.timedelta(days=REVIEW_INTERVAL_REFRESH)
    q = f"SELECT tconst FROM title_basics WHERE  tconst NOT IN (SELECT imdb_id FROM {target_table} " \
    f"WHERE last_update > '{str(refresh_interval_date)}')"
    """
    # TODO facut metoda si pentru tratat update-urile de rating-uri.
    cursor.execute(q)
    if cursor.with_rows:
        return conn, cursor
    else:
        return None, None


def process_new_tmdb(id):
    tmdb = TMDB(convert_imdb_id(id), '', '')
    tmdb.get_data()
    return [
        id,
        tmdb.country,
        tmdb.lang,
        tmdb.ovrw,
        tmdb.score,
        tmdb.trailer,
        datetime.datetime.now(),
    ]


if __name__ == '__main__':
    get_extra_data()