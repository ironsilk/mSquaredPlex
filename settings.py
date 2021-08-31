import logging

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
    'watchlists': {
        'id': 'AUTO-INCREMENT',
        'movie_id': 'int(11)',
        'imdb_id': 'int(11)',
        'status': 'VARCHAR(128)',
        'excluded_torrents': 'TEXT',
        'is_downloaded': 'VARCHAR(128)',
    }
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
