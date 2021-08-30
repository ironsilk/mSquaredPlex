import logging

custom_settings = {
    # Mysql
    'mysql_db_name': 'plex_buddy',
    'mysql_host': 'broodmother.go.ro',
    'mysql_port': 5433,
    'mysql_user': 'root',
    'mysql_pass': 'pass',
}

# Routine settings
FLIST_ROUTINE_SLEEP_TIME = 12  # hrs

# TORR settings
API_URL = 'https://filelist.io/api.php'
USER = ''
PASSKEY = ''
TORR_API_HOST = 'localhost'  # Listening path for torrent API service.
TORR_API_PATH = '/torr_api'  # Listening path for torrent API service.
TORR_API_PORT = 9092  # Listening path for torrent API service.
TORR_HOST = 'localhost'  # Listening path for torrent RPC service.
TORR_PORT = 9091  # Listening path for torrent RPC service.
TORR_USER = ''
TORR_PASS = ''
TORR_HASH_KEY = 'this my hash key'  # Used to secure incoming calls to API
TORR_DOWNLOAD_FOLDER = '/movies'
TORR_SEED_FOLDER = '/movies'
TORR_KEEP_TIME = 5  # days, to be used in TORR_REFRESHER, check_seeding_status
TORR_CLEAN_ROUTINE_INTERVAL = 15  # minutes between torrent client status checks
NO_POSTER_PATH = 'no-poster.png'
TELEGRAM_AUTH_TEST_PATH = 'images/auth_test.png'
TELEGRAM_AUTH_APPROVE = 'images/approve.jpg'
TELEGRAM_IMDB_RATINGS = 'images/ratings.jpg'
MOVIE_HDRO = 19
MOVIE_4K = 26
SOAP_HD = 21
SOAP_4K = 27

# PLEX server settings
# How to get the plex token:
# https://digiex.net/threads/plex-guide-step-by-step-getting-plex-token.15402/
PLEX_HOST = 'http://192.168.1.99:32400'
PLEX_TOKEN = ''
PLEX_SERVER_NAME = ''  # Will also appear in emails sent
PLEX_ADMIN_EMAILS = ['mihai.vlad6@gmail.com']  # If you have multiple admins or other users which are not friends,
# you've got to mention their emails here unfortunately. Their name must be their email. Not tested tho, don't have
# plex pass.
# The account the TOKEN belongs to should always be first, AKA your account


# TMDB & OMDB
TMDB_API_KEY = ''
OMDB_API_KEY = ''
INSERT_RATE = 100
OMDB_API_LIMIT = 800

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

# First column will be the primary key, must be int.
table_columns = {
    'my_movies': {
        'imdb_id': 'INT(11)',
        'type': 'CHAR(32)',
        'my_score': 'float',
        'seen_date': 'DATETIME',
        'user': 'VARCHAR(256)',
    },
    'my_torrents': {
        'torr_id': 'INT(11)',
        'torr_client_id': 'INT(11)',
        'imdb_id': 'INT(11)',
        'resolution': 'int(11)',
        'status': 'CHAR(32)',
        'requested_by': 'VARCHAR(256)',
    },
    'tmdb_data': {
        'imdb_id': 'INT(11)',
        'country': 'VARCHAR(128)',
        'lang': 'VARCHAR(128)',
        'ovrw': 'TEXT',
        'tmdb_score': 'FLOAT',
        'trailer_link': 'VARCHAR(256)',
        'poster': 'VARCHAR(256)',
        'last_update_tmdb': 'DATETIME',
        'hit_tmdb': 'BOOL',
    },
    'omdb_data': {
        'imdb_id': 'INT(11)',
        'awards': 'VARCHAR(256)',
        'country': 'VARCHAR(128)',
        'lang': 'VARCHAR(128)',
        'meta_score': 'FLOAT',
        'rated': 'FLOAT',
        'rott_score': 'FLOAT',
        'omdb_score': 'FLOAT',
        'last_update_omdb': 'DATETIME',
        'hit_omdb': 'BOOL',
    },
    'users': {
        'telegram_chat_id': 'INT(11)',
        'telegram_name': 'VARCHAR(256)',
        'email': 'VARCHAR(256)',
        'imdb_id': 'int(11)',
        'scan_watchlist': 'BOOL',
        'email_newsletters': 'BOOL',
    },
}

# EMAIL settings
xml_trnt_path = r'C:\Users\mihai\Desktop\git\mSquaredPlex\views\new_trnt.xml'
template_path = r'C:\Users\mihai\Desktop\git\mSquaredPlex\views\email_filelist.html'
movie_template_path = r'C:\Users\mihai\Desktop\git\mSquaredPlex\views\_movie.html'
trnt_template_path = r'C:\Users\mihai\Desktop\git\mSquaredPlex\views\_torrent.html'
EMAIL_USER = ''
EMAIL_PASS = ''
EMAIL_HOSTNAME = 'smtp.gmail.com'


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
