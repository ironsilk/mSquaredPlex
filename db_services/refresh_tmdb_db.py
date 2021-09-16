import os

from utils import get_tmdb, update_many, TmdbMovie, get_all_imdb_movies, timing
from utils import logger
import pickle
import os.path

REVIEW_INTERVAL_REFRESH = int(os.getenv('REVIEW_INTERVAL_REFRESH'))
INSERT_RATE = int(os.getenv('INSERT_RATE'))


def get_tmdb_data():
    """
    populates the database with data from TMDB
    session_not_found are the IDs searched for and not found which can be passed to this function
    in order not to search for them again.
    Extra keys:
    Poze, Country, Lang, Ovrw(short descr), score, trailer_link,
    :return:
    """
    # New titles
    logger.info("Downloading data for new TMDB titles")
    # Try to open local file
    if os.path.isfile('tconst_data_tmdb.pkl'):
        with open('tconst_data_tmdb.pkl', 'rb') as fp:
            results = pickle.load(fp)
    else:
        logger.info("Local file not found, refreshing entire database.")
        results = get_all_imdb_movies().mappings().fetchall()
        results = [x['tconst'] for x in results]

    logger.info(f"We have {len(results)} items left to process in this iteration for TMDB.")
    tmdb_inserted = 0
    while results:
        try:
            batch = [results.pop(0) for idx in range(min(INSERT_RATE, len(results)))]
            batch = process_tmdb_items(batch)
            if batch:
                update_many(batch, TmdbMovie, TmdbMovie.imdb_id)
            # Save to pickle
            with open('tconst_data_tmdb.pkl', 'wb') as fp:
                pickle.dump(results, fp)
            tmdb_inserted += 1
            logger.info(f"Inserted {tmdb_inserted * INSERT_RATE} into TMDB database")
        except Exception as e:
            raise e
            logger.error(f"Some other erorr while updating TMDB data: {e}")
            return
    logger.info('Finishing routine...')


@timing
def process_tmdb_items(items):
    new_items = []
    for item in items:
        item = get_tmdb(item)
        if item:
            new_items.append(item)
    return new_items


if __name__ == '__main__':
    from pprint import pprint
    get_tmdb_data()


