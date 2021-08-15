import logging

custom_settings = {
    # Mysql
    'mysql_db_name': 'plex_buddy',
    'mysql_host': 'broodmother.go.ro',
    'mysql_port': 5433,
    'mysql_user': 'root',
    'mysql_pass': 'pass',
}

API_URL = 'https://filelist.io/api.php'
USER = ''
PASSKEY = ''
MAX_SIZE = 12000000000  # 12 GB
CONCURRENT_DOWNLOADS = 10  # How many torrents to download simultaneously
DOWNLOAD_DIR = '/Gmedia/Movies'
MOVIE_HDRO = 19
MOVIE_4K = 26
SOAP_HD = 21
SOAP_4K = 27

#TMDB
TMDB_API_KEY = ''
OMDB_API_KEY = ''
INSERT_BATCH_SIZE = 100

# For imdb DB dumps
IMDB_DB_REFRESH_INTERVAL = 30  # days
REVIEW_INTERVAL_REFRESH = 180  # days
DUMPS_URL = 'https://datasets.imdbws.com/'
DUMPS_PATH = r'C:\Users\mihai\Downloads'
DB_URI = "mysql://{u}:{p}@{hp}/{dbname}?charset=utf8".format(
    u=custom_settings['mysql_user'],
    p=custom_settings['mysql_pass'],
    hp=':'.join([custom_settings['mysql_host'], str(custom_settings['mysql_port'])]),
    dbname=custom_settings['mysql_db_name'],
)

'''
ID-uri categorii filelist
| id | name             |
+----+------------------+
|  1 | Filme SD         |
|  2 | Filme DVD        |
|  3 | Filme DVD-RO     |
|  4 | Filme HD         |
|  5 | FLAC             |
|  6 | Filme 4K         |
|  7 | XXX              |
|  8 | Programe         |
|  9 | Jocuri PC        |
| 10 | Jocuri Console   |
| 11 | Audio            |
| 12 | Videoclip        |
| 13 | Sport            |
| 14 | TV               |
| 15 | Desene           |
| 16 | Docs             |
| 17 | Linux            |
| 18 | Diverse          |
| 19 | Filme HD-RO      |
| 20 | Filme Blu-Ray    |
| 21 | Seriale HD       |
| 22 | Mobile           |
| 23 | Seriale SD       |
| 24 | Anime            |
| 25 | Filme 3D         |
| 26 | Filme 4K Blu-Ray |
| 27 | Seriale 4K   
'''

table_columns = {
    'my_movies': {
        'imdb_id': 'CHAR(32)',
        'type': 'CHAR(32)',
        'resolution': 'int(11)',
        'torr_id': 'int(11)',
    },
    'tmdb_data': {
        'imdb_id': 'CHAR(32)',
        'country': 'VARCHAR(128)',
        'lang': 'VARCHAR(128)',
        'ovrw': 'TEXT',
        'score': 'FLOAT',
        'trailer_link': 'VARCHAR(256)',
        'last_update': 'DATETIME'
    },
    'omdb_data': {
        'imdb_id': 'CHAR(32)',
        'awards': 'VARCHAR(256)',
        'country': 'VARCHAR(128)',
        'lang': 'VARCHAR(128)',
        'meta_score': 'FLOAT',
        'rated': 'FLOAT',
        'rott_score': 'FLOAT',
        'score': 'FLOAT',
        'last_update': 'DATETIME',
    },
}


# Logger settings
def setup_logger(name, log_file=None, level=logging.INFO):
    """Function to setup as many loggers as you want"""
    formatter = logging.Formatter('[%(asctime)s] {%(filename)s:%(lineno)d} [%(name)s] [%(levelname)s] --> %(message)s')
    out_handler = logging.StreamHandler()
    out_handler.setFormatter(formatter)
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(out_handler)
    if log_file:
        handler = logging.FileHandler(log_file, encoding='utf8')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


logger = setup_logger('PlexService')
