import base64
import datetime
import hashlib
import json
import logging
import os
import re
import xml.etree.ElementTree as ET
from functools import wraps
from time import time

import PTN
import imdb
import omdb.api as omdb_api
import requests
import tmdbsimple as tmdb_api
from Crypto.Cipher import ChaCha20
from dotenv import load_dotenv
from plexapi.server import PlexServer
from transmission_rpc import Client
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, ARRAY, \
    Float, MetaData, create_engine, select, desc, delete, inspect
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.dialects.postgresql import insert
load_dotenv()

# ENV variables
POSTGRES_DB = os.getenv('POSTGRES_DB')
POSTGRES_HOST = os.getenv('POSTGRES_HOST')
POSTGRES_PORT = os.getenv('POSTGRES_PORT')
POSTGRES_USER = os.getenv('POSTGRES_USER')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD')

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

REVIEW_INTERVAL_REFRESH = int(os.getenv('REVIEW_INTERVAL_REFRESH'))

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')

PASSKEY = os.getenv('PASSKEY')

DB_URI = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"


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

# DB ENGINE
engine = create_engine(DB_URI, encoding='utf-8', echo=False)

# declarative base class
Base = declarative_base()

# MetaData
META_DATA = MetaData(engine)
META_DATA.reflect(engine)


# Base = declarative_base(metadata=META_DATA)
# Base.prepare()


# an example mapping using the base
class User(Base):
    __tablename__ = 'user'

    telegram_chat_id = Column(Integer, primary_key=True)
    telegram_name = Column(String)
    email = Column(String)
    imdb_id = Column(Integer)
    scan_watchlist = Column(Boolean)
    email_newsletters = Column(Boolean)
    movies = relationship("Movie", back_populates="user")
    watchlist_items = relationship("Watchlist", back_populates="user")
    requested_torrents = relationship("Torrent", back_populates="requested_by")


class Movie(Base):
    __tablename__ = 'movie'

    id = Column(Integer, primary_key=True)
    imdb_id = Column(Integer)
    my_score = Column(Integer)
    seen_date = Column(DateTime)
    user_id = Column(Integer, ForeignKey('user.telegram_chat_id'))
    user = relationship("User", back_populates="movies")
    rating_status = Column(String)


class Torrent(Base):
    __tablename__ = 'torrent'

    torr_id = Column(Integer, primary_key=True)
    torr_name = Column(String)
    imdb_id = Column(Integer)
    resolution = Column(Integer)
    status = Column(String)
    requested_by_id = Column(Integer, ForeignKey('user.telegram_chat_id'))
    requested_by = relationship("User", back_populates="requested_torrents")


class Watchlist(Base):
    __tablename__ = 'watchlists'

    id = Column(Integer, primary_key=True)
    imdb_id = Column(Integer)
    user_id = Column(Integer, ForeignKey('user.telegram_chat_id'))
    user = relationship("User", back_populates="watchlist_items")
    status = Column(String)
    excluded_torrents = Column(ARRAY(Integer))
    is_downloaded = Column(String)


class TmdbMovie(Base):
    __tablename__ = 'tmdb_data'

    imdb_id = Column(Integer, primary_key=True)
    country = Column(String)
    lang = Column(String)
    ovrw = Column(String)
    tmdb_score = Column(Float)
    trailer_link = Column(String)
    poster = Column(String)
    last_update_tmdb = Column(DateTime)
    hit_tmdb = Column(Boolean)


class OmdbMovie(Base):
    __tablename__ = 'omdb_data'

    imdb_id = Column(Integer, primary_key=True)
    awards = Column(String)
    country = Column(String)
    lang = Column(String)
    meta_score = Column(Float)
    rated = Column(Float)
    rott_score = Column(Float)
    omdb_score = Column(Float)
    last_update_omdb = Column(DateTime)
    hit_omdb = Column(Boolean)


class TitleBasics(Base):
    __tablename__ = 'title_basics'

    tconst = Column(Integer, primary_key=True)
    runtimeMinutes = Column(Integer)
    titleType = Column(String)
    primaryTitle = Column(String)
    originalTitle = Column(String)
    isAdult = Column(Boolean)
    startYear = Column(Integer)
    endYear = Column(Integer)
    runtimeMinutes = Column(Integer)
    t_soundex = Column(String)


class NameBasics(Base):
    __tablename__ = 'name_basics'

    nconst = Column(Integer, primary_key=True)
    primaryName = Column(String)
    birthYear = Column(Integer)
    deathYear = Column(Integer)
    primaryProfession = Column(String)
    knownForTitles = Column(String)
    ns_soundex = Column(String)
    sn_soundex = Column(String)
    s_soundex = Column(String)


class TitleAkas(Base):
    __tablename__ = 'title_akas'

    titleId = Column(Integer, primary_key=True)
    ordering = Column(Integer)
    title = Column(String)
    region = Column(String)
    language = Column(String)
    types = Column(String)
    attributes = Column(String)
    isOriginalTitle = Column(String)
    t_soundex = Column(String)


class TitleCrew(Base):
    __tablename__ = 'title_crew'

    tconst = Column(Integer, primary_key=True)
    directors = Column(Integer)
    writers = Column(String)


class TitleEpisode(Base):
    __tablename__ = 'title_episode'

    tconst = Column(Integer, primary_key=True)
    parentTconst = Column(Integer)
    seasonNumber = Column(Integer)
    episodeNumber = Column(Integer)


class TitlePrincipals(Base):
    __tablename__ = 'title_principals'

    tconst = Column(Integer, primary_key=True)
    ordering = Column(Integer)
    nconst = Column(Integer)
    category = Column(String)
    job = Column(String)
    characters = Column(String)


class TitleRatings(Base):
    __tablename__ = 'title_ratings'

    tconst = Column(Integer, primary_key=True)
    averageRating = Column(Float)
    numVotes = Column(Integer)


def connect_db():
    return engine.connect()


def check_database():
    engine = create_engine(DB_URI, encoding='utf-8', echo=False)
    metadata = MetaData(engine)
    metadata.create_all()
    User.__table__.create(bind=engine, checkfirst=True)
    Movie.__table__.create(bind=engine, checkfirst=True)
    Torrent.__table__.create(bind=engine, checkfirst=True)
    Watchlist.__table__.create(bind=engine, checkfirst=True)
    TmdbMovie.__table__.create(bind=engine, checkfirst=True)
    OmdbMovie.__table__.create(bind=engine, checkfirst=True)


def check_movielib_database():
    if all([inspect(engine).has_table("title_basics"),
            inspect(engine).has_table("name_basics"),
            inspect(engine).has_table("title_akas"),
            inspect(engine).has_table("title_crew"),
            inspect(engine).has_table("title_episode"),
            inspect(engine).has_table("title_principals"),
            inspect(engine).has_table("title_ratings"),

            ]):
        return True
    else:
        return False


def get_omdb_api_limit():
    refresh_interval_date = datetime.datetime.now() - datetime.timedelta(days=1)
    conn = connect_db()
    stmt = select(OmdbMovie).where(OmdbMovie.last_update_omdb > refresh_interval_date)
    return conn.execute(stmt).mappings().all()


def get_new_imdb_titles_for_omdb():
    conn = connect_db()
    refresh_interval_date = datetime.datetime.now() - datetime.timedelta(days=REVIEW_INTERVAL_REFRESH)
    subquery = select(OmdbMovie.imdb_id).where(OmdbMovie.last_update_omdb > refresh_interval_date)
    stmt = select(TitleBasics.tconst).where(TitleBasics.tconst.not_in(subquery))
    stmt = stmt.order_by(desc(TitleBasics.tconst))
    return conn.execute(stmt)


def get_new_imdb_titles_for_tmdb():
    # TODO speed up this query, think of min/max id instead of anything else.
    conn = connect_db()
    refresh_interval_date = datetime.datetime.now() - datetime.timedelta(days=REVIEW_INTERVAL_REFRESH)
    subquery = select(TmdbMovie.imdb_id).where(TmdbMovie.last_update_tmdb > refresh_interval_date)

    stmt = select(TitleBasics.tconst).where(TitleBasics.tconst.not_in(subquery))
    stmt = stmt.order_by(desc(TitleBasics.tconst))
    return conn.execute(stmt)


def check_against_my_torrents(torrents):
    """
    Checks if passed torrents from filelist API are aready in my_torrents db.
    :param torrents:
    :return:
    """
    with engine.connect() as conn:
        stmt = select(Torrent.torr_id).where(Torrent.torr_id.in_([x['id'] for x in torrents]))
        result = conn.execute(stmt).mappings().fetchall()
    if result:
        return [object_as_dict(x) for x in result]


def check_against_user_movies(movies, email):
    """
    Checks if passed torrents from filelist API are aready in my_torrents db.
    :param torrents:
    :return:
    """
    with engine.connect() as conn:
        stmt = select(Movie).where(Movie.imdb_id.in_([x['imdb_id'] for x in movies]))\
            .where(Movie.user.has(User.email == email))
        result = conn.execute(stmt).mappings().fetchall()
    return [object_as_dict(x) for x in result]


def check_against_user_watchlist(movies, user_imdb_id):
    with engine.connect() as conn:
        stmt = select(Watchlist).where(Watchlist.imdb_id.in_(movies))\
            .where(Movie.user.has(User.imdb_id == user_imdb_id))
        result = conn.execute(stmt).mappings().fetchall()
    return [object_as_dict(x) for x in result]


def check_one_against_torrents_by_imdb(idd):
    with engine.connect() as conn:
        stmt = select(Torrent).where(Torrent.imdb_id == idd)
        result = conn.execute(stmt).mappings().fetchall()
    return [object_as_dict(x) for x in result]


def check_one_against_torrents_by_torr_id(idd):
    with engine.connect() as conn:
        stmt = select(Torrent).where(Torrent.torr_id == idd)
        result = conn.execute(stmt).mappings().fetchall()
    return [object_as_dict(x) for x in result]


def check_one_against_torrents_by_torr_name(name):
    with engine.connect() as conn:
        stmt = select(Torrent).where(Torrent.torr_name == name)
        result = conn.execute(stmt).mappings().fetchall()
    return [object_as_dict(x) for x in result]


def get_movie_details(item):
    # ID
    try:
        imdb_id_number = deconvert_imdb_id(item['imdb'])
    except:
        imdb_id_number = deconvert_imdb_id(item['imdb_id'])
    # Search in local_db
    new_keys = get_movie_imdb(imdb_id_number)
    # Search online if TMDB, OMDB not found in local DB
    if not new_keys:
        return None
    tmdb_omdb = get_movie_tmdb_omdb(imdb_id_number)
    if tmdb_omdb:
        new_keys.update(tmdb_omdb)
    return {**item, **new_keys}


def get_movie_imdb(imdb_id):
    ia = imdb.IMDb('s3', DB_URI)
    try:
        movie = ia.get_movie(imdb_id)
        for key in ['cast', 'genres', 'kind', 'rating', 'title', 'original title', 'year',
                    'votes', 'runtimes', 'rating', 'director']:
            if key not in movie.data.keys():
                movie.data[key] = None
        item = {
            'cast': ', '.join([x['name'] for x in movie.data['cast'][:5]]) if movie.data['cast'] else None,
            'genres': ', '.join(movie.data['genres']) if movie.data['genres'] else None,
            'imdbID': movie.movieID,
            'titleType': movie.data['kind'],
            'averageRating': movie.data['rating'],
            'title': movie.data['title'],
            'originalTitle': movie.data['original title'],
            'startYear': movie.data['year'],
            'numVotes': movie.data['votes'],
            'runtimeMinutes': movie.data['runtimes'][0] if movie.data['runtimes'] else None
        }

    except Exception as e:
        raise e
        logger.error(f"IMDB fetch error: {e}")
        return None
    return item


def get_movie_tmdb_local(imdb_id):
    with engine.connect() as conn:
        stmt = select(TmdbMovie).where(TmdbMovie.imdb_id == imdb_id)
        result = conn.execute(stmt)
    if result:
        return object_as_dict(result.mappings().fetchone())


def get_movie_omdb_local(imdb_id):
    with engine.connect() as conn:
        stmt = select(OmdbMovie).where(OmdbMovie.imdb_id == imdb_id)
        result = conn.execute(stmt)
    if result:
        return object_as_dict(result.mappings().fetchone())


def get_movie_tmdb_omdb(imdb_id):
    tmdb = get_movie_tmdb_local(imdb_id)
    if not tmdb:
        tmdb = get_tmdb(imdb_id)
        if tmdb['hit_tmdb']:
            update_many([tmdb], TmdbMovie, TmdbMovie.imdb_id)
    omdb = get_movie_omdb_local(imdb_id)
    if not omdb:
        omdb = get_omdb(imdb_id)
        if omdb['hit_omdb']:
            update_many([omdb], OmdbMovie, OmdbMovie.imdb_id)
    return {**tmdb, **omdb}


def get_my_movie_by_imdb(idd):
    with engine.connect() as conn:
        stmt = select(Movie).where(Movie.imdb_id == idd)
        result = conn.execute(stmt)
    if result:
        return object_as_dict(result.mappings().fetchone())


def get_unrated_movies():
    with engine.connect() as conn:
        stmt = select(Movie).where(Movie.my_score.is_(None)).where(Movie.rating_status.is_(None))
        result = conn.execute(stmt)
    if result:
        return [object_as_dict(x) for x in result.mappings().fetchall()]


def get_my_imdb_users():
    with engine.connect() as conn:
        return conn.execute(select(User)).mappings().all()


def get_torrents():
    with engine.connect() as conn:
        result = conn.execute(select(Torrent).where(Torrent.status != 'removed')).mappings().all()
    return [object_as_dict(x) for x in result]


def get_requested_torrents_for_tgram_user(tgram_id):
    with engine.connect() as conn:
        stmt = select(Torrent).where(Torrent.requested_by.has(User.telegram_chat_id == tgram_id))
        result = conn.execute(stmt).mappings().fetchall()
    if result:
        return [object_as_dict(x) for x in result]


def get_tgram_user_by_email(email):
    with engine.connect() as conn:
        stmt = select(User.telegram_chat_id).where(User.email == email)
        result = conn.execute(stmt)
    if result:
        return object_as_dict(result.mappings().fetchone())


def get_user_by_tgram_id(telegram_chat_id):
    with engine.connect() as conn:
        stmt = select(User).where(User.telegram_chat_id == telegram_chat_id)
        result = conn.execute(stmt)
    if result:
        return object_as_dict(result.mappings().fetchone())


def get_user_movies(user):
    with engine.connect() as conn:
        stmt = select(Movie).where(Movie.user.has(User.telegram_chat_id == user['telegram_chat_id']))
        result = conn.execute(stmt).mappings().fetchall()
    if result:
        return [object_as_dict(x) for x in result]


def get_user_watchlist(user_imdb_id):
    with engine.connect() as conn:
        stmt = select(Watchlist).where(Watchlist.user.has(User.imdb_id == user_imdb_id))
        result = conn.execute(stmt).mappings().fetchall()
    if result:
        return [object_as_dict(x) for x in result]


def get_from_watchlist_by_user_and_imdb(user_imdb_id, imdb_id):
    with engine.connect() as conn:
        stmt = select(Watchlist).where(Watchlist.user.has(User.imdb_id == user_imdb_id))\
            .where(Watchlist.imdb_id == imdb_id)
        result = conn.execute(stmt)
    if result:
        return object_as_dict(result.mappings().fetchone())


def get_from_watchlist_by_user_telegram_id_and_imdb(imdb_id, telegram_chat_id):
    with engine.connect() as conn:
        stmt = select(Watchlist).where(Watchlist.user.has(User.telegram_chat_id == telegram_chat_id))\
            .where(Watchlist.imdb_id == imdb_id)
        result = conn.execute(stmt)
    return object_as_dict(result.mappings().fetchone())


def get_new_watchlist_items():
    with engine.connect() as conn:
        stmt = select(Watchlist).where(Watchlist.status == 'new')
        result = conn.execute(stmt).mappings().fetchall()
    if result:
        return [object_as_dict(x) for x in result]


def update_many(items, table, primary_key):
    if items:
        with engine.connect() as conn:
            insert_statement = insert(table).values(items)
            update_columns = {col.name: col for col in insert_statement.excluded if col.name != primary_key.name}
            update_stmt = insert_statement.on_conflict_do_update(
                index_elements=[primary_key],
                set_=update_columns
            )
            result = conn.execute(update_stmt)
        return result


def remove_from_watchlist_except(except_items, user_imdb_id):
    with engine.connect() as conn:
        stmt = delete(Watchlist).where(Watchlist.user.has(User.imdb_id == user_imdb_id))\
            .where(Watchlist.imdb_id.notin_(except_items))
        result = conn.execute(stmt)
    return result


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


def get_torr_name(name):
    return PTN.parse(name)['title']


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


def object_as_dict(obj):
    if obj:
        return dict(obj)


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
class GenericMovie:

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


class OMDB(GenericMovie):

    def __init__(self, id_imdb):
        GenericMovie.__init__(self, id_imdb)
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


class TMDB(GenericMovie):

    def __init__(self, id_imdb, type_tmdb, id_tmdb, search_title=None, search_year=None):
        GenericMovie.__init__(self, id_imdb)
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
                    logger.error('err tmdb - could not detemine tmdb id (movie or tv) for: {0}'.format(self.id_tmdb))
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


# SQL examples and other notes:
"""
# left join example
stmt = select(TmdbMovie, OmdbMovie).join(OmdbMovie, TmdbMovie.imdb_id == OmdbMovie.imdb_id).\
    where(TmdbMovie.imdb_id == imdb_id)
"""


if __name__ == '__main__':
    from pprint import pprint
    # pprint(get_movie_tmdb(15380158))
    # pprint(get_movie_tmdb_omdb(15380158))
    # print(check_movielib_database())
    pprint(get_tmdb(15012054))





