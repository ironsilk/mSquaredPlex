import os
import time
from datetime import datetime

import requests
from tqdm import tqdm
from dateutil import parser as d_util
from dotenv import load_dotenv
from lxml import html

from imdb_dump_import import run_import
from settings import setup_logger

load_dotenv()

IMDB_DB_REFRESH_INTERVAL = int(os.getenv('IMDB_DB_REFRESH_INTERVAL'))
DUMPS_URL = os.getenv('DUMPS_URL')
DUMPS_PATH = os.getenv('DUMPS_PATH')
DB_URI = "mysql://{u}:{p}@{hp}/{dbname}?charset=utf8".format(
    u=os.getenv('MYSQL_USER'),
    p=os.getenv('MYSQL_PASS'),
    hp=':'.join([os.getenv('MYSQL_HOST'), os.getenv('MYSQL_PORT')]),
    dbname=os.getenv('MYSQL_DB_NAME'),
)

logger = setup_logger("IMDB_db_updater")


def fetch_database_dumps():
    logger.info('Downloading dumps...')
    dom = html.fromstring(requests.get(DUMPS_URL).content)
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


def run():
    # Extra check refresh interval has passed:
    if refresh_interval_elapsed():
        start_time = datetime.now()
        # Update IMDB DB
        update_imdb_db()
        time.sleep(2)
        # Loop
        end_time = datetime.now()
        save_last_run_time(end_time)
        if (end_time - start_time).days < IMDB_DB_REFRESH_INTERVAL:
            logger.info('Sleeping for {n} days.'.format(n=IMDB_DB_REFRESH_INTERVAL -
                                                          (end_time - start_time).days))
            time.sleep(IMDB_DB_REFRESH_INTERVAL * 3600 * 24 - (end_time - start_time).total_seconds())
    else:
        sleep_time = ((IMDB_DB_REFRESH_INTERVAL * 24 * 3600) - (datetime.now() - read_last_run_time()).total_seconds())
        logger.info('Sleeping for {n} days.'.format(n=round(sleep_time / 3600 / 24)))
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
