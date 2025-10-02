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
import requests
import tmdbsimple as tmdb_api
from Crypto.Cipher import ChaCha20
from dotenv import load_dotenv
from plexapi.server import PlexServer
from transmission_rpc import Client
from sqlalchemy import Column, Integer, BigInteger, String, DateTime, Boolean, ForeignKey, ARRAY, \
    Float, MetaData, create_engine, select, desc, delete, inspect, func, or_, UniqueConstraint, ForeignKeyConstraint, \
    update
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
TMDB_V4_API_KEY = os.getenv('TMDB_V4_API_KEY')

TORR_HASH_KEY = os.getenv('TORR_HASH_KEY')

TORR_KEEP_TIME = int(os.getenv('TORR_KEEP_TIME')) if os.getenv('TORR_KEEP_TIME') else 60
TORR_HOST = os.getenv('TORR_HOST')
TORR_PORT = int(os.getenv('TORR_PORT')) if os.getenv('TORR_PORT') else 9091
TRANSMISSION_USER = os.getenv('TRANSMISSION_USER')
TRANSMISSION_PASS = os.getenv('TRANSMISSION_PASS')
TORR_API_HOST = os.getenv('TORR_API_HOST')
TORR_API_PORT = os.getenv('TORR_API_PORT')
TORR_API_PATH = os.getenv('TORR_API_PATH')
TORR_SEED_FOLDER = os.getenv('TORR_SEED_FOLDER')
TORR_DOWNLOAD_FOLDER = os.getenv('TORR_DOWNLOAD_FOLDER')

REVIEW_INTERVAL_REFRESH = os.getenv('REVIEW_INTERVAL_REFRESH')

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
engine = create_engine(DB_URI, echo=False, isolation_level="AUTOCOMMIT")

# declarative base class
Base = declarative_base()

# MetaData
META_DATA = MetaData()
META_DATA.bind = engine
META_DATA.reflect(bind=engine)


# Base = declarative_base(metadata=META_DATA)
# Base.prepare()


# an example mapping using the base
class User(Base):
    __tablename__ = 'user'

    telegram_chat_id = Column(BigInteger, primary_key=True)
    telegram_name = Column(String)
    email = Column(String)
    imdb_id = Column(Integer)
    scan_watchlist = Column(Boolean)
    email_newsletters = Column(Boolean)
    user_type = Column(String)
    movies = relationship("Movie", back_populates="user")
    watchlist_items = relationship("Watchlist", back_populates="user")
    requested_torrents = relationship("Torrent", back_populates="requested_by")


class Movie(Base):
    __tablename__ = 'movie'

    id = Column(Integer, primary_key=True)
    imdb_id = Column(Integer)
    my_score = Column(Integer)
    seen_date = Column(DateTime)
    user_id = Column(BigInteger, ForeignKey('user.telegram_chat_id', ondelete='CASCADE'))
    user = relationship("User", back_populates="movies")
    rating_status = Column(String)

    # movie_imdb_id_user_id_key unique constraint
    UniqueConstraint(imdb_id, user_id)


class Torrent(Base):
    __tablename__ = 'torrent'

    id = Column(Integer, primary_key=True)
    torr_id = Column(Integer)
    torr_hash = Column(String)
    imdb_id = Column(Integer)
    resolution = Column(Integer)
    status = Column(String)
    requested_by_id = Column(BigInteger, ForeignKey('user.telegram_chat_id', ondelete='CASCADE'))
    requested_by = relationship("User", back_populates="requested_torrents")
    extra_grace_days = Column(Integer, default=0)


class OneTimePassword(Base):
    __tablename__ = 'onetimepasswords'

    password = Column(Integer, primary_key=True)
    expiry = Column(DateTime)
    user_type = Column(String)


class Watchlist(Base):
    __tablename__ = 'watchlists'

    id = Column(Integer, primary_key=True)
    imdb_id = Column(Integer)
    user_id = Column(BigInteger, ForeignKey('user.telegram_chat_id', ondelete='CASCADE'))
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
    rated = Column(String)
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
    engine = create_engine(DB_URI, echo=False, isolation_level="AUTOCOMMIT")
    metadata = MetaData()
    META_DATA.bind = engine
    metadata.create_all(bind=engine)
    User.__table__.create(bind=engine, checkfirst=True)
    Movie.__table__.create(bind=engine, checkfirst=True)
    Torrent.__table__.create(bind=engine, checkfirst=True)
    OneTimePassword.__table__.create(bind=engine, checkfirst=True)
    Watchlist.__table__.create(bind=engine, checkfirst=True)
    TmdbMovie.__table__.create(bind=engine, checkfirst=True)
    OmdbMovie.__table__.create(bind=engine, checkfirst=True)
    TitleBasics.__table__.create(bind=engine, checkfirst=True)
    NameBasics.__table__.create(bind=engine, checkfirst=True)
    TitleAkas.__table__.create(bind=engine, checkfirst=True)
    TitleCrew.__table__.create(bind=engine, checkfirst=True)
    TitleEpisode.__table__.create(bind=engine, checkfirst=True)
    TitlePrincipals.__table__.create(bind=engine, checkfirst=True)
    TitleRatings.__table__.create(bind=engine, checkfirst=True)


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
    refresh_interval_date = datetime.datetime.now() - datetime.timedelta(days=int(REVIEW_INTERVAL_REFRESH))
    subquery = select(OmdbMovie.imdb_id).where(OmdbMovie.last_update_omdb > refresh_interval_date)
    stmt = select(TitleBasics.tconst).where(TitleBasics.tconst.not_in(subquery))
    stmt = stmt.order_by(desc(TitleBasics.tconst))
    return conn.execute(stmt)


def get_new_imdb_titles_for_tmdb():
    conn = connect_db()
    refresh_interval_date = datetime.datetime.now() - datetime.timedelta(days=int(REVIEW_INTERVAL_REFRESH))
    subquery = select(TmdbMovie.imdb_id).where(TmdbMovie.last_update_tmdb > refresh_interval_date)

    stmt = select(TitleBasics.tconst).where(TitleBasics.tconst.not_in(subquery))
    stmt = stmt.order_by(desc(TitleBasics.tconst))
    return conn.execute(stmt)


def get_all_imdb_movies():
    with engine.connect() as conn:
        stmt = select(TitleBasics.tconst).where(TitleBasics.titleType.in_(['movie', 'tvMovie', 'short']))
        stmt = stmt.order_by(desc(TitleBasics.tconst))
        result = conn.execute(stmt)
    return result


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
        stmt = select(Movie).where(Movie.imdb_id.in_([x['imdb_id'] for x in movies])) \
            .where(Movie.user.has(User.email == email))
        result = conn.execute(stmt).mappings().fetchall()
    return [object_as_dict(x) for x in result]


def check_against_user_watchlist(movies, user_imdb_id):
    with engine.connect() as conn:
        stmt = select(Watchlist).where(Watchlist.imdb_id.in_(movies)) \
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


def check_one_against_torrents_by_torr_hash(hash):
    with engine.connect() as conn:
        stmt = select(Torrent).where(Torrent.torr_hash == hash) \
            .where(Torrent.status.in_(['requested download', 'downloading']))
        result = conn.execute(stmt).mappings().fetchall()
    return [object_as_dict(x) for x in result]


def get_movie_details(item):
    # ID
    try:
        imdb_id_number = deconvert_imdb_id(item['imdb'])
    except KeyError:
        imdb_id_number = deconvert_imdb_id(item['imdb_id'])
    except AttributeError:
        return None
    # Search on IMDB
    new_keys = get_movie_imdb(imdb_id_number)
    # Search online if TMDB, OMDB not found in local DB
    if not new_keys:
        return None
    tmdb_omdb = get_movie_tmdb_omdb(imdb_id_number)
    if tmdb_omdb:
        new_keys.update(tmdb_omdb)
    return {**item, **new_keys}


def get_movie_imdb(imdb_id):
    ia = imdb.IMDb()
    try:
        movie = ia.get_movie(imdb_id)
        for key in ['cast', 'genres', 'kind', 'rating', 'title', 'original title', 'year',
                    'votes', 'runtimes', 'rating']:
            if key not in movie.data.keys():
                movie.data[key] = None
        item = {
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
        for key in ['cast', 'directors']:
            try:
                item[key] = ', '.join([x['name'] for x in movie.data[key][:5]]) if movie.data[key] else None
            except KeyError:
                item[key] = None
        try:
            item['countries'] = ', '.join([x for x in movie.data['countries'][:5]]) if movie.data['countries'] else None
        except KeyError:
            item[key] = None

    except Exception as e:
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
        del omdb['response']
        if omdb['hit_omdb']:
            update_many([omdb], OmdbMovie, OmdbMovie.imdb_id)

    return {**tmdb, **omdb}


def get_my_movie_by_imdb(idd, telegram_id):
    with engine.connect() as conn:
        stmt = select(Movie).where(Movie.imdb_id == idd).where(Movie.user_id == telegram_id)
        result = conn.execute(stmt)
    if result:
        return object_as_dict(result.mappings().fetchone())


def get_unrated_movies():
    with engine.connect() as conn:
        stmt = select(Movie).where(Movie.my_score.is_(None)).where(Movie.rating_status.is_(None))
        result = conn.execute(stmt)
    if result:
        return [object_as_dict(x) for x in result.mappings().fetchall()]


def get_movies_for_bulk_rating(telegram_id, status='bulk unrated'):
    with engine.connect() as conn:
        stmt = select(Movie).where(or_(Movie.rating_status == status, Movie.rating_status.is_(None))) \
            .where(Movie.user.has(User.telegram_chat_id == telegram_id))
        result = conn.execute(stmt)
    if result:
        return [object_as_dict(x) for x in result.mappings().fetchall()]


def get_my_imdb_users():
    with engine.connect() as conn:
        return conn.execute(select(User)).mappings().all()


def get_torrents(excluded_statuses=None):
    if excluded_statuses is None:
        excluded_statuses = ['removed', 'user notified (email)']
    with engine.connect() as conn:
        result = conn.execute(select(Torrent).where(Torrent.status.notin_(
            excluded_statuses
        ))).mappings().all()
    return [object_as_dict(x) for x in result]


def get_requested_torrents_for_tgram_user(tgram_id):
    with engine.connect() as conn:
        stmt = select(Torrent).where(Torrent.requested_by.has(User.telegram_chat_id == tgram_id))
        result = conn.execute(stmt).mappings().fetchall()
    if result:
        return [object_as_dict(x) for x in result]


def get_torrent_by_torr_id_user(torr_id, user_telegram):
    with engine.connect() as conn:
        stmt = select(Torrent).where(Torrent.torr_id == torr_id).where(Torrent.requested_by_id == user_telegram)
        result = conn.execute(stmt)
    if result:
        return object_as_dict(result.mappings().fetchone())


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


def ensure_user_exists(telegram_chat_id: int, telegram_name: str = None, email: str = None, imdb_id: int = None):
    """
    Ensure a User row exists for the given Telegram chat id.
    Upsert minimal fields; safe to call frequently.
    """
    # Prepare item for upsert; do not overwrite fields with None
    item = {"telegram_chat_id": telegram_chat_id}
    if telegram_name is not None:
        item["telegram_name"] = telegram_name
    if email is not None:
        item["email"] = email
    if imdb_id is not None:
        item["imdb_id"] = imdb_id

    # Uses update_many with primary key to perform upsert
    update_many([item], User, User.telegram_chat_id)
    return get_user_by_tgram_id(telegram_chat_id)


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
        stmt = select(Watchlist).where(Watchlist.user.has(User.imdb_id == user_imdb_id)) \
            .where(Watchlist.imdb_id == imdb_id)
        result = conn.execute(stmt)
    if result:
        return object_as_dict(result.mappings().fetchone())


def get_from_watchlist_by_user_telegram_id_and_imdb(imdb_id, telegram_chat_id):
    with engine.connect() as conn:
        stmt = select(Watchlist).where(Watchlist.user.has(User.telegram_chat_id == telegram_chat_id)) \
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


def update_many_multiple_pk(items, table, primary_keys):
    if items:
        with engine.connect() as conn:
            insert_statement = insert(table).values(items)
            update_columns = {col.name: col for col in insert_statement.excluded
                              if col.name not in [x.name for x in primary_keys]}
            update_stmt = insert_statement.on_conflict_do_update(
                index_elements=primary_keys,
                set_=update_columns
            )
            result = conn.execute(update_stmt)
        return result


def update_torrent_status(torr_id, status):
    with engine.connect() as conn:
        stmt = update(Torrent).where(Torrent.torr_id == torr_id).values(status=status)
        result = conn.execute(stmt)
    return result


def update_torrent_status_by_pk(db_id, status):
    """
    Update torrent status by primary key id as a fallback when torr_id is unavailable in row mappings.
    """
    with engine.connect() as conn:
        stmt = update(Torrent).where(Torrent.id == db_id).values(status=status)
        result = conn.execute(stmt)
    return result

def update_torrent_status_by_hash(hash_str, status):
    """
    Update torrent status by torrent hash as a fallback when torr_id does not match any row.
    """
    with engine.connect() as conn:
        stmt = update(Torrent).where(Torrent.torr_hash == hash_str).values(status=status)
        result = conn.execute(stmt)
    return result


def update_torrent_grace_days(torr_id, telegram_id, days=TORR_KEEP_TIME):
    with engine.connect() as conn:
        stmt = update(Torrent).where(Torrent.torr_id == torr_id)\
            .where(Torrent.requested_by.has(User.telegram_chat_id == telegram_id))\
            .values(extra_grace_days=Torrent.extra_grace_days + days)
        result = conn.execute(stmt)
    return result


def insert_many(items, table):
    if items:
        with engine.connect() as conn:
            stmt = insert(table).values(items)
            result = conn.execute(stmt)
        return result


def remove_from_watchlist_except(except_items, user_imdb_id):
    with engine.connect() as conn:
        stmt = delete(Watchlist).where(Watchlist.user.has(User.imdb_id == user_imdb_id)) \
            .where(Watchlist.imdb_id.notin_(except_items))
        result = conn.execute(stmt)
    return result


def get_onetimepasswords():
    with engine.connect() as conn:
        # return [x[0] for x in conn.execute(select(OneTimePassword)).all()]
        return conn.execute(select(OneTimePassword)).mappings().fetchall()


def insert_onetimepasswords(item):
    with engine.connect() as conn:
        stmt = insert(OneTimePassword).values([item])
        result = conn.execute(stmt)
    return result


def remove_onetimepassword(pwd):
    with engine.connect() as conn:
        stmt = delete(OneTimePassword).where(OneTimePassword.password == pwd)
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


def get_omdb(idd):
    r = requests.get(
        url="https://www.omdbapi.com/",
        params={
            'i': convert_imdb_id(idd),
            'apikey': OMDB_API_KEY,
        },
    )
    item = r.json()
    if item['Response'] == 'False':
        logger.debug("OMDB retrieve problems")
        return {
            'imdb_id': idd,
            'awards': None,
            'country': None,
            'lang': None,
            'rated': None,
            'rott_score': None,
            'omdb_score': None,
            'meta_score': None,
            'last_update_omdb': datetime.datetime.now(),
            'hit_omdb': False,
            'response': item['Error'],
        }
    item = {
        'imdb_id': idd,
        'awards': item['Awards'],
        'country': item['Country'],
        'lang': item['Language'],
        'rated': item['Rated'],
        'rott_score': try_or(lambda: [''.join([s for s in x['Value'] if s.isdigit()])
                                      for x in item['Ratings'] if x['Source'] == 'Rotten Tomatoes'][0]),
        'omdb_score': item['Metascore'],
        'meta_score': try_or(
            lambda: [x['Value'].split('/')[0] for x in item['Ratings'] if x['Source'] == 'Metacritic'][0]),
        'last_update_omdb': datetime.datetime.now(),
        'hit_omdb': True,
        'response': 'Ok',
    }
    for key, val in item.items():
        if val == 'N/A':
            item[key] = None
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
    return Client(host=TORR_HOST, port=TORR_PORT, username=TRANSMISSION_USER, password=TRANSMISSION_PASS)


def send_torrent(item, transmission_client=None):
    if not transmission_client:
        transmission_client = Client(host=TORR_HOST, port=TORR_PORT, username=TRANSMISSION_USER, password=TRANSMISSION_PASS)
    return transmission_client.add_torrent(item, download_dir=TORR_DOWNLOAD_FOLDER)


def parse_torr_name(name):
    return PTN.parse(name)


def try_or(func, default=None, expected_exc=(Exception,)):
    try:
        return func()
    except expected_exc as e:
        return default


def _title_header(title, original_title, year):
    if original_title:
        return f"{title}\n({original_title})\nYear: {year}\n"
    else:
        return f"{title}\nYear: ({year})\n"


# SQL examples and other notes:
"""
# left join example
stmt = select(TmdbMovie, OmdbMovie).join(OmdbMovie, TmdbMovie.imdb_id == OmdbMovie.imdb_id).\
    where(TmdbMovie.imdb_id == imdb_id)
"""

if __name__ == '__main__':
    # pkg = {'id': 54, 'imdb_id': 110912, 'my_score': None, 'seen_date': datetime.datetime(2021, 9, 2, 9, 0, 43), 'user_id': 1700079840, 'rating_status': None}
    # get_movie_details(pkg)
    client = make_client()
    client.remove_torrent([361866], delete_data=True)