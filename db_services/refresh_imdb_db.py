import os

import requests
from lxml import html

from imdb_dump_import import run_import
from utils import setup_logger

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
            for data in response.iter_content(chunk_size=1024):
                handle.write(data)

    logger.info('Dumps ready.')


def update_imdb_db():
    # Download latest dumps
    fetch_database_dumps()
    # Update database with 'em
    run_import(DB_URI, DUMPS_PATH)


if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()
    update_imdb_db()
