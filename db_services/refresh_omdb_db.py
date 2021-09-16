import os
import pickle

from utils import setup_logger, get_omdb, get_omdb_api_limit, OmdbMovie, update_many, \
    get_all_imdb_movies

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
    # Try to open local file
    if os.path.isfile('tconst_data_omdb.pkl'):
        with open('tconst_data_omdb.pkl', 'rb') as fp:
            results = pickle.load(fp)
    else:
        logger.info("Local file not found, refreshing entire database.")
        results = get_all_imdb_movies().mappings().fetchall()
        results = [x['tconst'] for x in results]

    # Get how many API calls we have left
    executed_calls = len(get_omdb_api_limit())
    if executed_calls > OMDB_API_LIMIT:
        logger.info('Hit OMDB API limit. Finishing up.')
        return
    else:
        calls_to_make = OMDB_API_LIMIT - executed_calls
    logger.info(f"We have {calls_to_make} API calls left.")
    logger.info(f"We have {len(results)} items left to process in this iteration for OMDB.")

    while results:
        try:
            if calls_to_make == 0:
                logger.info("Hit maximum calls, ending loop.")
                break
            elif (calls_to_make - INSERT_RATE) < 0:
                go = calls_to_make
            else:
                go = INSERT_RATE
            batch = [results.pop(0) for idx in range(go)]
            new_items = []
            for idx, item in enumerate(batch):
                item = get_omdb(item)
                if item['response'] not in ['Ok', 'Error getting data.']:
                    # We've hit API limit
                    logger.info(f"Hit maximum calls or key problem: {item['response']} -> ending loop.")
                    calls_to_make = 0
                    return
                del item['response']
                new_items.append(item)
            if new_items:
                update_many(new_items, OmdbMovie, OmdbMovie.imdb_id)
            # Save to pickle
            with open('tconst_data_omdb.pkl', 'wb') as fp:
                pickle.dump(results, fp)
            logger.info(f"Inserted {len(batch)} into OMDB database out of {go} searches.")
            calls_to_make -= go
            logger.info(f"We have {calls_to_make} API calls left.")
        except Exception as e:
            raise e
            logger.error(f"Some other erorr while pulling IMDB data: {e}")
            return


if __name__ == '__main__':
    get_omdb_data()
