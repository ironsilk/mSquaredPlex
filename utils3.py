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
import mysql.connector as cnt
import mysql.connector.errors
import omdb.api as omdb_api
import requests
import tmdbsimple as tmdb_api
from Crypto.Cipher import ChaCha20
from dotenv import load_dotenv
from mysql.connector.errors import InterfaceError, DatabaseError, ProgrammingError
from plexapi.server import PlexServer
from transmission_rpc import Client
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import declarative_base

from utils import get_movie_tmdb_omdb

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

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')

PASSKEY = os.getenv('PASSKEY')

DB_URI = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

# DB queries




if __name__ == '__main__':
    from pprint import pprint
    pprint(get_requested_torrents_for_tgram_user(1700079840))

