from utils import logger
import requests
from settings import API_URL, USER, PASSKEY, MOVIE_HDRO, MOVIE_4K, SOAP_HD, SOAP_4K
from db_tools import check_in_my_movies
from pprint import pprint

# https://filelist.io/forums.php?action=viewtopic&topicid=120435


def get_latest_torrents(n=100, category=MOVIE_HDRO):
    '''
    returns last n movies from filelist API.
    n default 100
    movie category default HD RO
    '''
    logger.info('Getting RSS feeds')
    r = requests.get(
        url=API_URL,
        params={
            'username': USER,
            'passkey': PASSKEY,
            'action': 'latest-torrents',
            'category': category,
            'limit': n,
        },
    )
    if category == MOVIE_4K:
        return [x for x in r.json() if 'Remux' in x['name']]
    return r.json()


def filter_results(new_movies):
    filtered = check_in_my_movies(new_movies)
    return filtered


def run():
    # fetch latest movies
    new_movies = get_latest_torrents()


    # filter out those already in database with same or better quality and mark
    # the rest if they are already in db
    filtered_movies = filter_results(new_movies)
    pprint(filtered_movies[:3])

    # get IMDB, TMDB and OMDB data for these new movies.


    # send to user to choose or choose automatically.


    # download and update database.


















if __name__ == '__main__':
    run()
