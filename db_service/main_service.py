from datetime import datetime
import time
from imdb_db import update_imdb_db
from settings import IMDB_DB_REFRESH_INTERVAL, logger
from dateutil import parser as d_util


def run():
    # Extra check refresh interval has passed:
    if refresh_interval_elapsed():
        start_time = datetime.now()
        # Update IMDB DB
        # update_imdb_db()
        # Get extra data

        time.sleep(2)
        # Loop
        end_time = datetime.now()
        save_last_run_time(end_time)
        if (end_time - start_time).days < IMDB_DB_REFRESH_INTERVAL:
            logger.info('Sleeping for {n} days.'.format(n=IMDB_DB_REFRESH_INTERVAL -
                                                          (end_time - start_time).days))
            time.sleep(IMDB_DB_REFRESH_INTERVAL * 60 * 24 - (end_time - start_time).total_seconds())
    else:
        sleep_time = (IMDB_DB_REFRESH_INTERVAL * 24 * 60 - (datetime.now() - read_last_run_time()).total_seconds())
        logger.info('Sleeping for {n} days.'.format(n=round(sleep_time / 60 / 24)))
        time.sleep(sleep_time)
    run()


def save_last_run_time(time):
    f = open("last_update.txt", "w")
    f.write(time.strftime("%d/%m/%Y, %H:%M:%S"))
    f.close()


def refresh_interval_elapsed():
    last_run = read_last_run_time()
    if not last_run:
        return True
    if (datetime.now() - last_run).days > IMDB_DB_REFRESH_INTERVAL:
        return True
    return False


def read_last_run_time():
    try:
        with open('last_update.txt', 'rb') as f:
            time = f.read()
        return d_util.parse(time)
    except FileNotFoundError:
        return None


if __name__ == '__main__':
    run()
    # read_last_run_time()
