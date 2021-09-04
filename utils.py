import logging
import os

import imdb
import mysql.connector as cnt
import mysql.connector.errors
import requests
from plexapi.server import PlexServer
import re
import xml.etree.ElementTree as ET
import PTN
import omdb.api as omdb_api
import tmdbsimple as tmdb_api
import datetime
from Crypto.Cipher import ChaCha20
import hashlib
import base64
import json
from time import time
from functools import wraps
from transmission_rpc import Client

from dotenv import load_dotenv

load_dotenv()

# ENV variables
MYSQL_DB_NAME = os.getenv('MYSQL_DB_NAME')
MYSQL_HOST = os.getenv('MYSQL_HOST')
MYSQL_PORT = os.getenv('MYSQL_PORT')
MYSQL_USER = os.getenv('MYSQL_USER')
MYSQL_PASS = os.getenv('MYSQL_PASS')

MYSQL_MYIMDB_DB_NAME = os.getenv('MYSQL_MYIMDB_DB_NAME')
MYSQL_MYIMDB_HOST = os.getenv('MYSQL_MYIMDB_HOST')
MYSQL_MYIMDB_PORT = os.getenv('MYSQL_MYIMDB_PORT')
MYSQL_MYIMDB_USER = os.getenv('MYSQL_MYIMDB_USER')
MYSQL_MYIMDB_PASS = os.getenv('MYSQL_MYIMDB_PASS')

PLEX_HOST = os.getenv('PLEX_HOST')
PLEX_TOKEN = os.getenv('PLEX_TOKEN')
PLEX_SERVER_NAME = os.getenv('PLEX_SERVER_NAME')
PLEX_ADMIN_EMAILS = os.getenv('PLEX_ADMIN_EMAILS')

OMDB_API_KEY = os.getenv('OMDB_API_KEY')
TMDB_API_KEY = os.getenv('TMDB_API_KEY')

TORR_HASH_KEY = os.getenv('TORR_HASH_KEY')

TORR_KEEP_TIME = int(os.getenv('TORR_KEEP_TIME'))
TORR_HOST = os.getenv('TORR_HOST')
TORR_PORT = int(os.getenv('TORR_PORT'))
TORR_USER = os.getenv('TORR_USER')
TORR_PASS = os.getenv('TORR_PASS')
TORR_API_HOST = os.getenv('TORR_API_HOST')
TORR_API_PORT = os.getenv('TORR_API_PORT')
TORR_API_PATH = os.getenv('TORR_API_PATH')
TORR_SEED_FOLDER = os.getenv('TORR_SEED_FOLDER')
TORR_DOWNLOAD_FOLDER = os.getenv('TORR_DOWNLOAD_FOLDER')

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')

PASSKEY = os.getenv('PASSKEY')


table_columns_plexbuddy = {
    'my_movies': {
        'imdb_id': 'INT(11)',
        'type': 'CHAR(32)',
        'my_score': 'float',
        'seen_date': 'DATETIME',
        'user': 'VARCHAR(256)',
        'rating_status': 'VARCHAR(128)',
    },
    'my_torrents': {
        'torr_id': 'INT(11)',
        'torr_name': 'TEXT',
        'imdb_id': 'INT(11)',
        'resolution': 'int(11)',
        'status': 'CHAR(32)',
        'requested_by': 'TEXT',
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

table_columns_myimdb = {
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


# Setup a logger
logger = setup_logger("PlexUtils")


# Primitive db interractions
def connect_mysql(myimdb=False):
    # Connects to mysql and returns cursor
    if not myimdb:
        sql_conn = cnt.connect(host=MYSQL_HOST, port=MYSQL_PORT,
                               database=MYSQL_DB_NAME,
                               user=MYSQL_USER, password=MYSQL_PASS)
    else:
        sql_conn = cnt.connect(host=MYSQL_MYIMDB_HOST, port=MYSQL_MYIMDB_PORT,
                               database=MYSQL_MYIMDB_DB_NAME,
                               user=MYSQL_MYIMDB_USER, password=MYSQL_MYIMDB_PASS)
    return sql_conn, sql_conn.cursor(dictionary=True)


def close_mysql(conn, cursor):
    conn.close()
    return


def create_db(name):
    sql_conn = cnt.connect(
        host=MYSQL_HOST, port=MYSQL_PORT,
        user=MYSQL_USER, password=MYSQL_PASS)
    sql_conn.cursor().execute("CREATE DATABASE {x}".format(x=name))
    sql_conn.close()


def check_db_plexbuddy():
    logger.info("Checking DB at service startup")
    try:
        conn, cursor = connect_mysql()
    except mysql.connector.errors.ProgrammingError:  # if db doesn't exist, create it
        create_db(MYSQL_DB_NAME)
        conn, cursor = connect_mysql()
    # Check all tables defined in settings.py, table_columns.
    for table, columns in table_columns_plexbuddy.items():
        check_table(
            cursor,
            table=table,
            columns=list(columns.keys()),
            column_types=columns,
            db=MYSQL_DB_NAME,
        )
    close_mysql(conn, cursor)
    logger.info("All tables OK.")


def check_db_myimdb():
    logger.info("Checking DB at service startup")
    try:
        conn, cursor = connect_mysql(myimdb=True)
    except mysql.connector.errors.ProgrammingError:  # if db doesn't exist, create it
        sql_conn = cnt.connect(
            host=MYSQL_MYIMDB_HOST, port=MYSQL_MYIMDB_PORT,
            user=MYSQL_MYIMDB_USER, password=MYSQL_MYIMDB_PASS)
        sql_conn.cursor().execute("CREATE DATABASE {x}".format(x=MYSQL_MYIMDB_DB_NAME))
        sql_conn.close()
        conn, cursor = connect_mysql()
    # Check all tables defined in settings.py, table_columns.
    for table, columns in table_columns_myimdb.items():
        check_table(
            cursor,
            table=table,
            columns=list(columns.keys()),
            column_types=columns,
            db=MYSQL_MYIMDB_DB_NAME,
        )
    close_mysql(conn, cursor)
    logger.info("All tables OK.")


def check_table(cursor, table, columns, column_types, db):
    q = '''
    SELECT table_name FROM information_schema.tables WHERE table_name = '{table}' AND table_schema = '{db_name}'
    '''.format(db_name=db, table=table)
    cursor.execute(q)
    result = cursor.fetchone()
    if result:
        pass
    else:
        logger.info("Table '{table}' does not exist, creating...".format(table=table))
        primary_key = columns.pop(0)
        if column_types[primary_key] == 'AUTO-INCREMENT':
            auto_increment = True
        else:
            auto_increment = False

        del column_types[primary_key]
        q = f'''
        CREATE TABLE `{table}` (
        `{primary_key}` int(11) NOT NULL,
        PRIMARY KEY (`{primary_key}`) KEY_BLOCK_SIZE=1024
        ) ENGINE=MyISAM AUTO_INCREMENT=0 DEFAULT CHARSET=utf8mb4 ROW_FORMAT=COMPRESSED KEY_BLOCK_SIZE=8;
        '''
        if auto_increment:
            q = q.replace('int(11) NOT NULL', 'int(11) NOT NULL AUTO_INCREMENT')
        cursor.execute(q)
        for col in columns:
            try:
                query = "ALTER TABLE {table} ADD {column} {col_type}".format(table=table, column=col,
                                                                             col_type=column_types[col])
                cursor.execute(query)
            except Exception as e:
                logger.error(e)
                raise e
        logger.info("Done! Table created.")


def insert_sql(chunk, table, columns):
    '''
    Inserts chunk into sql, if it fails
    it fallsback to row insert and errors get logged into
    a local error log file.
    '''
    conn, cursor = connect_mysql()
    placeholder = ", ".join(["%s"] * len(columns))
    stmt = "INSERT into `{table}` ({columns}) values ({values});".format(table=table, columns=",".join(columns),
                                                                         values=placeholder)
    try:
        cursor.executemany(stmt, chunk)
        conn.commit()
    except Exception as e:
        logger.error("Error {e} inserting chunk into mysql, falling back to atomic insert".format(e=e))
        for item in chunk:
            atomic_insert_sql(item, conn, cursor, table, columns)
    close_mysql(conn, cursor)


def atomic_insert_sql(item, conn, cursor, table, columns):
    """
    Inserts into mysql one row at a time and returns the ID.
    """
    placeholder = ", ".join(["%s"] * len(columns))
    stmt = "INSERT into `{table}` ({columns}) values ({values});".format(table=table,
                                                                         columns=",".join(columns),
                                                                         values=placeholder)
    try:
        cursor.execute(stmt, item)
        conn.commit()
        r = {
            'status': "Ok",
            'id': cursor.lastrowid
        }
    except Exception as e:
        r = {
            'status': e,
            'id': None
        }
    return r


def update_one(update_columns, update_values, condition_col, condition_value, table, conn=None, cursor=None):
    # Update_columns and update values must be lists with same length such as:
    # new_name=Somename, new_age=Someage etc.
    # Condition col will mostly be the primary key and cond values will be the ids.
    if not cursor:
        conn, cursor = connect_mysql()
    set_statement = ", ".join(
        ['''`{col}` = "{value}"'''.format(col=col, value=val) for col, val in zip(update_columns, update_values)])
    stmt = '''UPDATE `{table}` SET {set_statement} WHERE `{condition_col}` = '{value}' '''.format(
        table=table,
        set_statement=set_statement,
        condition_col=condition_col,
        value=condition_value)
    try:
        cursor.execute(stmt)
        conn.commit()
    except cnt.errors.IntegrityError as e:
        logger.error('Got {e}'.format(e=e))


def update_many(data_list=None, mysql_table=None, connection=None, cursor=None):
    """
    Updates a mysql table with the data provided. If the key is not unique, the
    data will be inserted into the table.

    The dictionaries must have all the same keys due to how the query is built.

    Param:
        data_list (List):
            A list of dictionaries where the keys are the mysql table
            column names, and the values are the update values
        mysql_table (String):
            The mysql table to be updated.
    """

    # Connection and Cursor
    if not cursor or not connection:
        connection, cursor = connect_mysql()

    query = ""
    values = []

    for data_dict in data_list:

        if not query:
            columns = ', '.join(['`{0}`'.format(k) for k in data_dict])
            duplicates = ', '.join(['{0}=VALUES({0})'.format(k) for k in data_dict])
            place_holders = ', '.join(['%s'.format(k) for k in data_dict])
            query = f"INSERT INTO {mysql_table} ({columns}) VALUES ({place_holders})"
            query = f"{query} ON DUPLICATE KEY UPDATE {duplicates}"

        v = list(data_dict.values())
        values.append(v)
    try:
        cursor.executemany(query, values)
    except Exception as e:
        logger.warning(f"UpdateMany MySQL Error: {e}")

        connection.rollback()
        return False

    connection.commit()
    cursor.close()
    connection.close()


# Misc tolls
def convert_imdb_id(id):
    '''
    289992 turns into tt0289992
    :param id:
    :return:
    '''
    if len(str(id)) < 7:
        return 'tt' + str(id).zfill(7)
    else:
        return 'tt' + str(id)


def deconvert_imdb_id(imdb_id):
    '''
    tt0289992 turns into 289992
    :param imdb_id:
    :return:
    '''
    if type(imdb_id) != int:
        return imdb_id.replace('tt', '').lstrip('0')
    return imdb_id


def get_torr_quality(name):
    return int(PTN.parse(name)['resolution'][:-1])


def timing(f):
    @wraps(f)
    def wrap(*args, **kw):
        ts = time()
        result = f(*args, **kw)
        te = time()
        logger.info(f"Function `{f.__name__}` execution time: {'%.2f' % (te - ts)} seconds")
        return result

    return wrap


def compose_link(id):
    return f'https://filelist.io/download.php?id={id}&passkey={PASSKEY}'


def send_message_to_bot(chat_id, message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage?chat_id={chat_id}&text={message}"
    r = requests.get(url)
    return r.json()['ok']

# DB queries
def get_my_imdb_users(cursor=None):
    if not cursor:
        conn, cursor = connect_mysql()
    q = """SELECT * from users"""
    cursor.execute(q)
    return cursor.fetchall()


def get_watchlist_for_user(user_imdb_id, cursor=None):
    if not cursor:
        conn, cursor = connect_mysql()
    q = f"SELECT * FROM watchlists WHERE imdb_id = {user_imdb_id} and status = 'new'"
    cursor.execute(q)
    return cursor.fetchall()


def check_one_in_my_torrents_by_imdb(idd, cursor=None):
    if not cursor:
        conn, cursor = connect_mysql()
    q = f"SELECT * FROM my_torrents WHERE imdb_id = {idd}"
    cursor.execute(q)
    return cursor.fetchall()


def check_one_in_my_torrents_by_torr_id(idd, cursor=None):
    if not cursor:
        conn, cursor = connect_mysql()
    q = f"SELECT * FROM my_torrents WHERE torr_id = {idd}"
    cursor.execute(q)
    return cursor.fetchone()


def check_one_in_my_torrents_by_torr_name(name, cursor=None):
    if not cursor:
        conn, cursor = connect_mysql()
    q = f"SELECT * FROM my_torrents WHERE torr_name = '{name}'"
    cursor.execute(q)
    return cursor.fetchone()


def retrieve_one_from_dbs(item, cursor=None):
    if not cursor:
        try:
            conn, cursor = connect_mysql(myimdb=True)
        except mysql.connector.errors.DatabaseError:
            conn, cursor = None, None
    # ID
    imdb_id_number = deconvert_imdb_id(item['imdb'])
    # Search in local_db
    imdb_keys = get_movie_IMDB(imdb_id_number, cursor)
    # Search online if TMDB, OMDB not found in local DB
    if not imdb_keys:
        return None
    if imdb_keys['hit_tmdb'] != 1:
        tmdb = get_tmdb(imdb_id_number)
        if tmdb['hit_tmdb'] == 1:
            imdb_keys.update(tmdb)
            # Update db
            update_many([tmdb], 'tmdb_data')
    if imdb_keys['hit_omdb'] != 1:
        omdb = get_omdb(imdb_id_number)
        if omdb['hit_omdb'] == 1:
            imdb_keys.update(omdb)
            # Update db
            update_many([omdb], 'omdb_data')
    return {**item, **imdb_keys}


def get_movie_IMDB(imdb_id, cursor=None):
    item = get_movie_from_local_db(imdb_id, cursor)
    if not item:
        item = get_movie_from_imdb_online(imdb_id)
    if item:
        item['hit_tmdb'] = 0
        item['hit_omdb'] = 0
    return item


def get_movie_from_local_db(imdb_id, cursor):
    try:
        if not cursor:
            conn, cursor = connect_mysql(myimdb=True)
        q = f"""SELECT a.*, b.numVotes, b.averageRating, e.title, c.*, d.* FROM title_basics a
        left join title_ratings b on a.tconst = b.tconst
        left join tmdb_data c on a.tconst = c.imdb_id
        left join omdb_data d on a.tconst = d.imdb_id
        left join title_akas e on a.tconst = e.titleId
        where a.tconst = {imdb_id} AND e.isOriginalTitle = 1

        """
        q_crew = f"""SELECT group_concat(primaryName) as 'cast' 
        FROM name_basics WHERE nconst in 
        (SELECT nconst FROM title_principals where tconst = {imdb_id} and category = 'actor')
        """

        q_director = f"""SELECT primaryName as 'director' FROM name_basics 
        WHERE nconst = (SELECT directors FROM title_crew  where tconst = {imdb_id})
        """

        cursor.execute(q)
        item = cursor.fetchone()
        if not item:
            return None
        # Add crew
        cursor.execute((q_crew))
        item.update(cursor.fetchone())

        # Add director
        cursor.execute((q_director))
        item.update(**cursor.fetchone())
    except (mysql.connector.errors.DatabaseError, mysql.connector.errors.ProgrammingError) as e:
        logger.warning(f"IMDB db is down or programming error: {e}")
        return None
    return item


def get_movie_from_imdb_online(imdb_id):
    ia = imdb.IMDb()
    try:
        movie = ia.get_movie(imdb_id)
        if 'rating' not in movie.data.keys():
            movie.data['rating'] = None
        item = {
            'cast': ', '.join([x['name'] for x in movie.data['cast'][:5]]),
            'director': movie.data['director'][0].data['name'],
            'genres': ', '.join(movie.data['genres']),
            'imdbID': movie.data['imdbID'],
            'titleType': movie.data['kind'],
            'averageRating': movie.data['rating'],
            'title': movie.data['title'],
            'originalTitle': movie.data['localized title'],
            'startYear': movie.data['year'],
            'numVotes': movie.data['votes'],
            'runtimeMinutes': movie.data['runtimes'][0]
        }

    except Exception as e:
        logger.error(f"IMDB online error: {e}")
        item = None
    return item


def get_tgram_user_by_email(email, cursor=None):
    if not cursor:
        conn, cursor = connect_mysql()
    q = f"SELECT `telegram_chat_id` FROM users where email = '{email}'"
    cursor.execute(q)
    return cursor.fetchone()['telegram_chat_id']


# PLEX utils
def connect_plex():
    # Server
    plex = PlexServer(PLEX_HOST, PLEX_TOKEN)
    # Account
    account = plex.myPlexAccount()
    return account, plex


def get_plex_users(account=None, plex=None):
    if not account:
        account, plex = connect_plex()
    return account.users()


# TMDB OMDB classes
class Movie:

    def __init__(self, id_imdb):
        self.id_list = []
        self.id_imdb = id_imdb
        self.title = None
        self.year = None
        self.country = None
        self.score = None

    def get_movie_dblist(self, xml_path):
        try:
            XMLtree = ET.parse(xml_path)
            XMLroot = XMLtree.getroot()
            for child in XMLroot:
                self.id_list.append(child.find('imdb_id').text)

        except Exception:
            logger.debug('get_movie_dblist err')


class OMDB(Movie):

    def __init__(self, id_imdb):
        Movie.__init__(self, id_imdb)
        self.genre = None
        self.lang = None
        self.imdb_score = None
        self.rott_score = None
        self.meta_score = None
        self.rated = None
        self.awards = None
        self.director = None
        self.actors = None
        self.apikey_omdb = OMDB_API_KEY

    def get_data(self):
        logger.debug('get_data {}'.format(self.id_imdb))

        try:
            omdb_api.set_default('apikey', self.apikey_omdb)
            raw_omdb = omdb_api.imdbid(self.id_imdb)
        except Exception:
            logger.debug('could not load JSON from omdb for id:{}'.format(self.id_imdb))
            return

        if 'title' in raw_omdb:
            self.title = raw_omdb['title']
        else:
            logger.debug('no "title" in omdb json')

        if 'year' in raw_omdb:
            self.year = raw_omdb['year']
        else:
            logger.debug('no "year" in omdb json')

        if 'country' in raw_omdb:
            self.country = raw_omdb['country']
        else:
            logger.debug('no "country" in omdb json')

        if 'genre' in raw_omdb:
            self.genre = raw_omdb['genre']
        else:
            logger.debug('no "genre" in omdb json')

        if 'language' in raw_omdb:
            self.lang = raw_omdb['language']
        else:
            logger.debug('no "language" in omdb json')

        if 'ratings' in raw_omdb:
            for data in raw_omdb['ratings']:
                if data['source'] == 'Internet Movie Database':
                    self.imdb_score = data['value'][:-3]
                elif data['source'] == 'Rotten Tomatoes':
                    self.rott_score = data['value'][:-1]
                elif data['source'] == 'Metacritic':
                    self.meta_score = data['value'][:-4]
        else:
            logger.debug('no "ratings" in omdb json')

        if 'rated' in raw_omdb:
            self.rated = raw_omdb['rated']
        else:
            logger.debug('no "rated" in omdb json')

        if 'awards' in raw_omdb:
            self.awards = raw_omdb['awards']
        else:
            logger.debug('no "awards" in omdb json')

        if 'director' in raw_omdb:
            self.director = raw_omdb['director']
        else:
            logger.debug('no "director" in omdb json')

        if 'actors' in raw_omdb:
            self.actors = raw_omdb['actors']
        else:
            logger.debug('no "actors" in omdb json')


class TMDB(Movie):

    def __init__(self, id_imdb, type_tmdb, id_tmdb, search_title=None, search_year=None):
        Movie.__init__(self, id_imdb)
        self.genre = None
        self.url = None
        self.lang = None
        self.runtime = None
        self.ovrw = None
        self.poster = None
        self.trailer = None
        self.cast = None
        self.director = None
        self.backdrops = None
        self.type_tmdb = type_tmdb
        self.id_tmdb = id_tmdb
        self.apikey_tmdb = TMDB_API_KEY
        self.search_title = search_title
        self.search_year = search_year
        self.search_result = None

    def get_data(self):
        logger.debug('get_data {0} / {1} {2}'.format(self.id_imdb, self.type_tmdb, self.id_tmdb))
        tmdb_api.API_KEY = self.apikey_tmdb

        if self.id_imdb == '':
            if self.id_tmdb != '':
                if 'movie' in self.type_tmdb:
                    self.tmdb_movie()
                elif 'tv' in self.type_tmdb:
                    self.tmdb_tv()
                else:
                    print('err tmdb - could not detemine tmdb id (movie or tv) for: {0}'.format(self.id_tmdb))
            elif self.search_title is not None:
                self.tmdb_search()
                logger.debug('to search')
        else:
            try:
                logger.debug('is imdb')
                find = tmdb_api.Find(self.id_imdb)
                response = find.info(external_source='imdb_id')
                if find.movie_results:
                    self.id_tmdb = find.movie_results[0]['id']
                    self.tmdb_movie()
                else:
                    logger.debug('0 results for movie - id imdb:{}'.format(self.id_imdb))
                    if find.tv_results:
                        self.id_tmdb = find.tv_results[0]['id']
                        self.tmdb_tv()
                    else:
                        logger.debug('0 results for tv shows - id imdb:{}'.format(self.id_imdb))
                        return
            except Exception:
                logger.debug('err tmdb - id=tt. Response is: {}'.format(response))
                return

        if self.country is not None:
            cntry_dict = {'United States of America': 'USA', 'United Kingdom': 'UK', 'GB': 'UK', 'FR': 'France',
                          'US': 'USA', 'DE': 'Germany', 'RU': 'Russia'}
            for country_long, country_short in cntry_dict.items():
                self.country = re.sub(r'\b%s\b' % country_long, country_short, self.country)

        if self.lang is not None:
            lang_dict = {'en': 'English', 'es': 'Espanol', 'fr': 'Francais', 'de': 'Deutsch', 'pl': 'Polski',
                         'shqip': 'Albanian', 'bi': 'Bislama', 'ky': 'Kirghiz', 'tl': 'Tagalog', 'ny': 'Chichewa',
                         'st': 'Southern Sotho', 'xh': 'Xhosa', 'hi': 'Hindi', 'tn': 'Tswana'}
            for lang_short, lang_long in lang_dict.items():
                self.lang = re.sub(r'\b%s\b' % lang_short.lower(), lang_long, self.lang)
            self.lang = self.lang.title()

    def tmdb_movie(self):
        logger.debug('tmdb_movie {0}'.format(self.id_tmdb))

        self.type_tmdb = 'movie'

        try:
            movie = tmdb_api.Movies(self.id_tmdb)
            response = movie.info()
        # print response
        except Exception:
            logger.debug('could not load JSON from tmdb for movie id:{}'.format(self.id_tmdb))
            return

        try:
            self.id_imdb = movie.imdb_id
        except Exception:
            logger.debug('')

        try:
            self.url = 'https://www.themoviedb.org/movie/{0}'.format(movie.id)
        except Exception:
            logger.debug('')

        try:
            self.title = movie.title
        except Exception:
            logger.debug('')

        try:
            self.year = movie.release_date[:4]
        except Exception:
            logger.debug('')

        # obtine doar primele 4 genre
        try:
            if movie.genres:
                genre = movie.genres[0]['name']
                for x in range(3):
                    try:
                        genre = '{0}, {1}'.format(genre, movie.genres[x + 1]['name'])
                    except:
                        break
                self.genre = genre
            else:
                logger.debug('no "genre" value available')
        except Exception:
            logger.debug('')

        # obtine doar primele 4 country
        try:
            if movie.production_countries:
                country = movie.production_countries[0]['name']
                for x in range(3):
                    try:
                        country = '{0}, {1}'.format(country, movie.production_countries[x + 1]['name'])
                    except:
                        break
                self.country = country
            else:
                logger.debug('no "production_countries" value available')
        except Exception:
            logger.debug('')

        # obtine doar primele 4 lang
        try:
            if movie.spoken_languages:
                lang = movie.spoken_languages[0]['name']
                if lang == '' or lang == '??????':
                    lang = movie.spoken_languages[0]['iso_639_1']
                    logger.debug('weird lang - iso_639_1 code is:{}'.format(lang))
                for x in range(3):
                    try:
                        if movie.spoken_languages[x + 1]['name'] != '':
                            lang = '{0}, {1}'.format(lang, movie.spoken_languages[x + 1]['name'])
                        else:
                            lang = '{0}, {1}'.format(lang, movie.spoken_languages[x + 1]['iso_639_1'])
                            logger.debug('weird lang - iso_639_1 code is:{}'.format(lang))
                    except:
                        break
                self.lang = lang
            else:
                logger.debug('no "languages" value available')
        except Exception:
            logger.debug('')

        try:
            self.score = movie.vote_average
        except Exception:
            logger.debug('')

        try:
            self.runtime = movie.runtime
        except Exception:
            logger.debug('')

        try:
            self.ovrw = movie.overview.replace('\n', '').replace('\r', '')
        except Exception:
            logger.debug('')

        try:
            self.poster = 'https://image.tmdb.org/t/p/w300_and_h450_bestv2{0}'.format(movie.poster_path)
        except Exception:
            logger.debug('')

        try:
            response = movie.videos()
        except Exception:
            logger.debug('')

        try:
            for x in movie.results:
                if x['type'] == 'Trailer' and x['site'] == 'YouTube':
                    if x['key'] is not None:
                        self.trailer = 'https://www.youtube.com/watch?v={0}'.format(x['key'])
                    break
        except Exception:
            logger.debug('')

        try:
            response = movie.credits()
        except Exception:
            logger.debug('')

        try:
            temp_cast = ''
            for s in movie.cast[:5]:
                temp_cast = '{0}, {1}'.format(temp_cast, s['name'].encode('utf-8'))
            self.cast = temp_cast[2:]
        except Exception:
            logger.debug('')

        try:
            for s in movie.crew:
                if s['job'] == 'Director':
                    self.director = s['name']
        except Exception:
            logger.debug('')

        try:
            response = movie.images()
        except Exception:
            logger.debug('')

        try:
            backdrops = []
            for s in movie.backdrops:
                backdrops.append('http://image.tmdb.org/t/p/w1280{0}'.format(s['file_path']))
            self.backdrops = backdrops
        except Exception:
            logger.debug('')

    def tmdb_tv(self):
        logger.debug('tmdb_tv {0}'.format(self.id_tmdb))

        self.type_tmdb = 'tv'

        try:
            tv = tmdb_api.TV(self.id_tmdb)
            response = tv.info()
        except Exception:
            logger.debug('')

        try:
            self.url = 'https://www.themoviedb.org/tv/{0}'.format(self.id_tmdb)
        except Exception:
            logger.debug('')

        try:
            self.title = tv.name
        except Exception:
            logger.debug('')

        try:
            self.year = tv.first_air_date[:4]
        except Exception:
            logger.debug('')

        try:
            if tv.genres:
                genre = tv.genres[0]['name']
                for x in range(3):
                    try:
                        genre = '{0}, {1}'.format(genre, tv.genres[x + 1]['name'])
                    except:
                        break
                self.genre = genre
            else:
                logger.debug('no "genre" value available')
        except Exception:
            logger.debug('')

        # obtine doar primele 4 country
        try:
            if tv.origin_country:
                if 'name' in tv.origin_country[0]:
                    country = tv.origin_country[0]['name']
                else:
                    country = tv.origin_country[0]
                for x in range(3):
                    try:
                        if 'name' in tv.origin_country[0]:
                            country = '{0}, {1}'.format(country, tv.origin_country[x + 1]['name'])
                        else:
                            country = '{0}, {1}'.format(country, tv.origin_country[x + 1])
                    except:
                        break
                self.country = country
            else:
                logger.debug('no "origin_country" value available')
        except Exception:
            logger.debug('')

        # obtine doar primele 4 lang
        try:
            if tv.languages:
                if 'name' in tv.languages:
                    lang = tv.languages[0]['name']
                else:
                    lang = tv.languages[0]
                for x in range(3):
                    try:
                        if 'name' in tv.languages[0]:
                            lang = '{0}, {1}'.format(lang, tv.languages[x + 1]['name'])
                        else:
                            lang = '{0}, {1}'.format(lang, tv.languages[x + 1])
                    except:
                        break
                self.lang = lang
            else:
                logger.debug('no "languages" value available')
        except Exception:
            logger.debug('')

        try:
            self.score = tv.vote_average
        except Exception:
            logger.debug('')

        try:
            self.ovrw = tv.overview.replace('\n', '').replace('\r', '')
        except Exception:
            logger.debug('')

        try:
            self.poster = 'https://image.tmdb.org/t/p/w300_and_h450_bestv2{0}'.format(tv.poster_path)
        except Exception:
            logger.debug('')

        try:
            response = tv.videos()
        except Exception:
            logger.debug('')

        try:
            for x in tv.results:
                if x['type'] == 'Trailer' and x['site'] == 'YouTube':
                    if x['key'] is not None:
                        self.trailer = 'https://www.youtube.com/watch?v={0}'.format(x['key'])
                    break
        except Exception:
            logger.debug('')

        try:
            response = tv.credits()
        except Exception:
            logger.debug('')

        try:
            temp_cast = ''
            for s in tv.cast[:5]:
                temp_cast = '{0}, {1}'.format(temp_cast, s['name'].encode('utf-8'))
            self.cast = temp_cast[2:]
        except Exception:
            logger.debug('')

        try:
            for s in tv.crew:
                if s['job'] == 'Director':
                    self.director = s['name']
        except Exception:
            logger.debug('')

        try:
            response = tv.images()
        except Exception:
            logger.debug('')

        try:
            backdrops = []
            for s in tv.backdrops:
                backdrops.append('http://image.tmdb.org/t/p/w1280{0}'.format(s['file_path']))
            self.backdrops = backdrops
        except Exception:
            logger.debug('')

    def tmdb_search(self):
        logger.debug('tmdb_search movie title & year: {0} {1}'.format(self.search_title, self.search_year))
        try:
            search = tmdb_api.Search()
            response = search.movie(query=self.search_title)
        # print response
        except Exception:
            logger.debug('')

        try:
            for s in search.results:
                if self.search_year is not None and self.search_year == int(s['release_date'][:4]):
                    self.title = s['title']
                    self.id_tmdb = s['id']
                    self.year = int(s['release_date'][:4])
                    self.score = s['popularity']
                    self.search_result = 'based on title and year'
                    break
            if self.id_tmdb is None:
                self.title = s['title']
                self.id_tmdb = s['id']
                self.year = int(s['release_date'][:4])
                self.score = s['popularity']
                self.search_result = 'based only on title'
        except Exception:
            logger.debug('')


def get_omdb(idd):
    omdb = OMDB(convert_imdb_id(idd))
    omdb.get_data()
    try:
        rated = float(omdb.rated)
    except (ValueError, TypeError):
        rated = None

    if all(v is None for v in [omdb.awards, omdb.country, omdb.lang, omdb.meta_score, omdb.rott_score, omdb.score]):
        hit = False
    else:
        hit = True

    item = {
        'imdb_id': idd,
        'awards': omdb.awards,
        'country': omdb.country,
        'lang': omdb.lang,
        'meta_score': omdb.meta_score,
        'rated': rated,
        'rott_score': omdb.rott_score,
        'omdb_score': omdb.score,
        'last_update_omdb': datetime.datetime.now(),
        'hit_omdb': hit,
    }
    return item


def get_tmdb(idd):
    tmdb = TMDB(convert_imdb_id(idd), '', '')
    tmdb.get_data()

    if all(v is None for v in [tmdb.country, tmdb.lang, tmdb.ovrw, tmdb.score, tmdb.trailer]):
        hit = False
    else:
        hit = True

    item = {
        'imdb_id': idd,
        'country': tmdb.country,
        'lang': tmdb.lang,
        'ovrw': tmdb.ovrw,
        'tmdb_score': tmdb.score,
        'trailer_link': tmdb.trailer,
        'poster': tmdb.poster,
        'last_update_tmdb': datetime.datetime.now(),
        'hit_tmdb': hit,
    }
    return item


# CYPHER utils
class AESCipher(object):

    def __init__(self, key):
        self.key = hashlib.sha256(key.encode()).digest()
        self.nonce = 'QWT8HeQOuSU='

    def encrypt(self, raw):
        cipher = ChaCha20.new(key=self.key, nonce=self.nonce)
        ciphertext = cipher.encrypt(str.encode(raw))
        ct = base64.b64encode(ciphertext).decode('utf-8')
        return ct

    def decrypt(self, enc):
        cipher = ChaCha20.new(key=self.key, nonce=self.nonce)
        ciphertext = base64.b64decode(enc)
        plaintext = cipher.decrypt(ciphertext)
        return json.loads(plaintext)


torr_cypher = AESCipher(TORR_HASH_KEY)


# TORR utils
def make_client():
    return Client(host=TORR_HOST, port=TORR_PORT, username=TORR_USER, password=TORR_PASS)


def send_torrent(item, transmission_client=None):
    if not transmission_client:
        transmission_client = Client(host=TORR_HOST, port=TORR_PORT, username=TORR_USER, password=TORR_PASS)
    return transmission_client.add_torrent(item, download_dir=TORR_DOWNLOAD_FOLDER)


def parse_torr_name(name):
    return PTN.parse(name)


if __name__ == '__main__':
    from pprint import pprint
    # check_db_plexbuddy()

