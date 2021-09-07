import os

import requests
from lxml import html

from imdb_dump_import import run_import
from utils import setup_logger, check_db_myimdb

# Alternatives, maybe:
# https://stackoverflow.com/questions/1231900/mysql-load-data-local-infile-example-in-python
# https://dev.mysql.com/doc/refman/8.0/en/load-data.html

IMDB_DB_REFRESH_INTERVAL = int(os.getenv('IMDB_DB_REFRESH_INTERVAL'))
DUMPS_URL = os.getenv('DUMPS_URL')
DUMPS_PATH = os.getenv('DUMPS_PATH')
DB_URI = "postgresql+psycopg2://{u}:{p}@{hp}/{dbname}".format(
    u='mike',
    p='pass',
    hp=':'.join(['192.168.1.99', '5432']),
    dbname='movielib',
)
DB_URI = "postgresql://mike:pass@192.168.1.99/movielib"

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
    # fetch_database_dumps()
    # Update database with 'em
    run_import(DB_URI, DUMPS_PATH)


if __name__ == '__main__':
    # check_db_myimdb()
    print(DB_URI)
    update_imdb_db()
