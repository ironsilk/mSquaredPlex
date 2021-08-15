# WIP
from utils import logger
import requests
from settings import API_URL, USER, PASSKEY, MOVIE_HDRO, MOVIE_4K, SOAP_HD, SOAP_4K
from pprint import pprint









def get_fl_movie(movie_id):
    r = requests.get(
        url=API_URL,
        params={
            'username': USER,
            'passkey': PASSKEY,
            'action': 'search-torrents',
            'query': movie_id,
            'type': 'imdb',
            'category': MOVIE_HDRO,
        },
    )
    return r.json()