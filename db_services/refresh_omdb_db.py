import os

from utils import setup_logger, get_omdb, get_omdb_api_limit, get_new_imdb_titles_for_omdb, OmdbMovie, update_many

logger = setup_logger('OMDB_refresher')

REVIEW_INTERVAL_REFRESH = int(os.getenv('REVIEW_INTERVAL_REFRESH'))
OMDB_API_LIMIT = int(os.getenv('OMDB_API_LIMIT'))
INSERT_RATE = int(os.getenv('INSERT_RATE'))


def get_omdb_data():
    """
    populates the database with data from OMDB
    Extra keys:
    Poze, Country, Lang, Ovrw(short descr), score, trailer_link,
    :return:
    """
    # New titles
    logger.info("Downloading data for new OMDB titles")
    # Get how many API calls we have left
    executed_calls = len(get_omdb_api_limit())
    if executed_calls > OMDB_API_LIMIT:
        logger.info('Hit OMDB API limit. Finishing up.')
        return
    else:
        calls_to_make = OMDB_API_LIMIT - executed_calls
    logger.info(f"We have {calls_to_make} API calls left.")
    new_for_omdb_cursor = get_new_imdb_titles_for_omdb()
    while new_for_omdb_cursor.returns_rows:
        try:
            if (calls_to_make - INSERT_RATE) < 0:
                go = calls_to_make
            else:
                go = INSERT_RATE
            batch = new_for_omdb_cursor.mappings().fetchmany(go)
            batch = process_items(batch)
            update_many(batch, OmdbMovie, OmdbMovie.imdb_id)
            logger.info(f"Inserted {len(batch)} into OMDB database out of {go} searches.")
            calls_to_make -= go
            logger.info(f"We have {calls_to_make} API calls left.")
        except Exception as e:
            raise e
            logger.error(f"Some other erorr while pulling IMDB data: {e}")
            return


def process_items(items):
    new_items = []
    for item in items:
        item = get_omdb(item['tconst'])
        if not item['hit_omdb']:
            new_items.append(item)
        else:
            new_items.append(item)
    return new_items


if __name__ == '__main__':
    get_omdb_data()
