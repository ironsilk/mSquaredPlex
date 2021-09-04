import os

import imdb
import requests

from utils import check_one_in_my_torrents_by_imdb, retrieve_one_from_dbs
from utils import connect_mysql, update_many, connect_plex
from utils import deconvert_imdb_id, check_one_in_my_torrents_by_torr_id
from utils import setup_logger

NO_POSTER_PATH = os.getenv('NO_POSTER_PATH')

logger = setup_logger("BotUtils")


def make_movie_reply(pkg):
    caption = ''
    # Title
    title = _title_header(pkg['title'], pkg['originalTitle'], pkg['startYear'])
    if title:
        caption += title
    # Stars
    stars = rating_stars(pkg)
    if stars:
        caption += stars
    # Description
    if pkg['ovrw']:
        caption += pkg['ovrw'] + '\n'
    # Trailer
    trailer = make_trailer(pkg['trailer_link'])
    if trailer:
        caption += trailer
    # Image
    image = get_image(pkg['poster'])
    if not caption:
        caption = 'No info about this movie, strange.'
    return caption, image


def get_image(img):
    if img:
        r = requests.get(img)
        if r.status_code == 200:
            return r.content
    return open(NO_POSTER_PATH, 'rb')


def _title_header(title, original_title, year):
    if original_title:
        return f"{title}\n({original_title})\nYear: {year}\n"
    else:
        return f"{title}\nYear: ({year})\n"


def rating_stars(pkg):
    """Transforms int rating into stars with int"""
    stars = ''
    # IMDB
    if pkg['averageRating']:
        x = int(float(pkg['averageRating']) // 2)
        rating_stars = f"🎟️ IMDB: {'⭐ ' * x} {pkg['averageRating']}"
        if pkg['numVotes']:
            rating_stars += f" 🧑‍⚖️{pkg['numVotes']:,}\n"
        else:
            rating_stars += "\n"
        stars += rating_stars
    # rott_score
    if pkg['rott_score']:
        x = int(float(pkg['rott_score']) // 20)
        rating_stars = f"🍿 ROTTEN: {'⭐ ' * x} {pkg['rott_score']}\n"
        stars += rating_stars
    # meta_score
    if pkg['meta_score']:
        x = int(float(pkg['meta_score']) // 20)
        rating_stars = f"🚽 META: {'⭐ ' * x} {pkg['meta_score']}\n"
        stars += rating_stars
    # tmdb_score
    if pkg['tmdb_score']:
        x = int(float(pkg['tmdb_score']) // 2)
        rating_stars = f"🎬 TMDB: {'⭐ ' * x} {pkg['tmdb_score']}\n"
        stars += rating_stars
    return stars


def make_trailer(link):
    if link:
        return f"🎥: {link}"
    return None


def make_trailer_shorten_url(link):
    if link:
        try:
            # construct the request headers with authorization
            headers = {"Authorization": "Bearer ce9b5c5be30a86b343630452ed990a983a2ad623"}
            guid = 'Bl8sgmRT1By'
            # make the POST request to get shortened URL for `url`
            shorten_res = requests.post("https://api-ssl.bitly.com/v4/shorten",
                                        json={"group_guid": guid, "long_url": link},
                                        headers=headers)
            if shorten_res.status_code == 200:
                # if response is OK, get the shortened URL
                link = shorten_res.json().get("link")
            else:
                # Do, nothing, return the link as it is
                pass
        except Exception as e:
            print(e)
        return f"🎥: {link}"
    return None


def get_telegram_users():
    conn, cursor = connect_mysql()
    q = """SELECT * FROM users
    """
    cursor.execute(q)
    users = cursor.fetchall()
    return {
        x['telegram_chat_id']:
            {
                'email': x['email'],
                'imdb_id': x['imdb_id'],
                'telegram_name': x['telegram_name'],
                'scan_watchlist': x['scan_watchlist'],
                'email_newsletters': x['email_newsletters'],
            }
        for x in users}


def update_torr_db(pkg, torr_response, tgram_id):
    # Check if torrent is already requested
    torr = check_one_in_my_torrents_by_torr_id(pkg['id'])
    if torr:
        requesters = torr['requested_by'].split(',')
        requesters.append(get_email_by_tgram_id(tgram_id))
        requesters = ','.join(list(set(requesters)))
    else:
        requesters = get_email_by_tgram_id(tgram_id)

    update_many([{
        'torr_id': pkg['id'],
        'torr_name': torr_response.name,
        'imdb_id': deconvert_imdb_id(pkg['imdb']),
        'resolution': pkg['resolution'],
        'status': 'requested download',
        'requested_by': requesters
    }],
        'my_torrents')


def get_watchlist_item(movie_id, tg_id):
    conn, cursor = connect_mysql()
    q = f"SELECT * FROM watchlists WHERE movie_id = {movie_id} " \
        f"AND imdb_id = (SELECT imdb_id FROM users where telegram_chat_id = {tg_id})"
    cursor.execute(q)
    return cursor.fetchone()


def exclude_torrents_from_watchlist(movie_id, tg_id, torr_ids):
    new = ', '.join([str(x) for x in torr_ids])
    watchlist_item = get_watchlist_item(movie_id, tg_id)
    if watchlist_item['excluded_torrents']:
        old = watchlist_item['excluded_torrents'].split(', ')
        new = ', '.join([str(x) for x in torr_ids if x not in old])
    update_many([{
        'id': watchlist_item['id'],
        'movie_id': movie_id,
        'imdb_id': watchlist_item['imdb_id'],
        'excluded_torrents': new,
        'status': 'new',
    }],
        'watchlists')


def get_excluded_resolutions(movie_id, tg_id):
    excluded = get_watchlist_item(movie_id, tg_id)['excluded_torrents']
    if excluded:
        return [int(x) for x in excluded.split(', ')]
    else:
        return []


def invite_friend(email, account=None, plex=None):
    if not account:
        account, plex = connect_plex()
    try:
        account.inviteFriend(email, plex)
    except Exception as e:
        logger.error(e)
        return False
    return True


def get_movie_from_all_databases(imdb_id):
    new_movie = False
    conn, cursor = connect_mysql()
    # Check if it's in my_movies:
    my_item = check_one_in_my_movies(imdb_id, cursor)
    if not my_item:
        my_item = dict()
        new_movie = True
    # Check if it's in my_torrents
    torr_results = check_one_in_my_torrents_by_imdb(imdb_id, cursor)
    if torr_results:
        max_res_item = max(torr_results, key=lambda x: x['resolution'])
        my_item['torr_result'] = True
        my_item['torr_status'] = max_res_item['status']
        my_item['resolution'] = max_res_item['resolution']
    else:
        my_item['torr_result'] = False
    # Get rest of the data
    pkg = retrieve_one_from_dbs({'imdb': imdb_id}, cursor)
    if not pkg:
        return None
    if not new_movie:
        pkg['already_in_my_movies'] = True
        return {**pkg, **my_item}
    else:
        pkg['already_in_my_movies'] = False
        return pkg


def search_imdb_title(item, ia=None):
    if not ia:
        try:
            ia = imdb.IMDb()
        except Exception as e:
            logger.error(e)
            return 'IMDB library error'
    try:
        movies = ia.search_movie(item, _episodes=False)
        # return {x.movieID: x.data for x in movies}
        res = []
        for x in movies:
            if x.data['kind'] == 'movie':
                x.data['id'] = x.movieID
                res.append(x.data)
        return res
        # return {x.data for x in movies}
    except Exception as e:
        logger.error(e)
        return 'IMDB library error'


def check_one_in_my_movies(idd, cursor=None):
    if not cursor:
        conn, cursor = connect_mysql()
    q = f"SELECT * FROM my_movies WHERE imdb_id = {idd}"
    cursor.execute(q)
    return cursor.fetchone()


def get_email_by_tgram_id(user, cursor=None):
    if not cursor:
        conn, cursor = connect_mysql()
    q = f"SELECT `email` FROM users where telegram_chat_id = '{user}'"
    cursor.execute(q)
    return cursor.fetchone()['email']


def get_imdb_id_by_trgram_id(user, cursor=None):
    if not cursor:
        conn, cursor = connect_mysql()
    q = f"SELECT `imdb_id` FROM users where telegram_chat_id = '{user}'"
    cursor.execute(q)
    return cursor.fetchone()['imdb_id']


def add_to_watchlist(movie_id, imdb_id, status, excluded_torrents=None):

    # See if movie already there
    conn, cursor = connect_mysql()
    q = f"SELECT * FROM watchlists WHERE movie_id = {movie_id} " \
        f"AND imdb_id = {imdb_id}"
    cursor.execute(q)
    in_watchlist = cursor.fetchone()
    to_update = {
        'movie_id': movie_id,
        'imdb_id': imdb_id,
        'status': status,
        'excluded_torrents': None
    }
    if excluded_torrents:
        to_update['excluded_torrents'] = ', '.join([str(x) for x in excluded_torrents])
    if in_watchlist:
        to_update['id'] = in_watchlist['id']
        if in_watchlist['excluded_torrents']:
            if excluded_torrents:
                old = in_watchlist['excluded_torrents'].split(', ')
                new = list(set(old + excluded_torrents))
                to_update['excluded_torrents'] = ', '.join([str(x) for x in new])
            else:
                to_update['excluded_torrents'] = in_watchlist['excluded_torrents']

    update_many([to_update], 'watchlists')


if __name__ == '__main__':
    pass
