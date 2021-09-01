import os

import PTN
import requests
from telegram.ext import CallbackContext
import imdb
from utils import deconvert_imdb_id, get_my_imdb_users
from utils import connect_mysql, update_many, connect_plex, setup_logger, convert_imdb_id, get_torr_quality
from utils import check_one_in_my_torrents_by_imdb, retrieve_one_from_dbs

NO_POSTER_PATH = os.getenv('NO_POSTER_PATH')
API_URL = os.getenv('API_URL')
USER = os.getenv('USER')
PASSKEY = os.getenv('PASSKEY')

MOVIE_HDRO = os.getenv('MOVIE_HDRO')
MOVIE_4K = os.getenv('MOVIE_4K')


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
    update_many([{
        'torr_id': pkg['id'],
        'torr_client_id': torr_response.id,
        'imdb_id': deconvert_imdb_id(pkg['imdb']),
        'resolution': pkg['resolution'],
        'status': 'requested download',
        'requested_by': get_email_by_tgram_id(tgram_id)
    }],
        'my_torrents')


def bot_watchlist_routine(context: CallbackContext) -> None:
    """
    Gets newest watchlist items form database and if it finds the torrents
    for those movies it notifies the user.
    :param context:
    :return:
    """
    # Get watchlist items
    watchlist_items = get_watchlist_new()
    if watchlist_items:
        users = get_my_imdb_users()
        for item in watchlist_items:
            torrents = get_torrents_for_imdb_id(item['movie_id'])
            torrents = sorted(torrents, key=lambda k: k['size'])
            if item['excluded_torrents']:
                torrents = [x for x in torrents if str(x['id']) not in item['excluded_torrents']]
            if item['is_downloaded']:
                torrents = [x for x in torrents if str(x['resolution']) != item['is_downloaded']]

            if torrents:
                chat_id = [x['telegram_chat_id'] for x in users if x['imdb_id'] == item['imdb_id']][0]
                message = f"Hi there! WATCHLIST ALERT!\n"\
                          f"🎞️ {PTN.parse(torrents[0]['name'])['title']}\n"\
                          f"has {len(torrents)} download candidates\n"\
                          f"📥 /WatchMatch{item['movie_id']} (download)\n\n"\
                          f"❌ /UnWatchMatch{item['movie_id']} (forget movie)"
                if item['is_downloaded']:
                    message += f"\n🚨 Movie aleady exists in PLEX, quality: {item['is_downloaded']}"
                context.bot.send_message(chat_id=chat_id, text=message)
                # exclude_torrents_from_watchlist(item['movie_id'], chat_id, [x['id'] for x in torrents])
                update_watchlist_item_status(item['movie_id'], chat_id, 'notification sent')


def get_watchlist_item(movie_id, tg_id):
    conn, cursor = connect_mysql()
    q = f"SELECT * FROM watchlists WHERE movie_id = {movie_id} " \
        f"AND imdb_id = (SELECT imdb_id FROM users where telegram_chat_id = {tg_id})"
    cursor.execute(q)
    return cursor.fetchone()


def update_watchlist_item_status(movie_id, tg_id, new_status):
    watchlist_item = get_watchlist_item(movie_id, tg_id)
    update_many([{
        'id': watchlist_item['id'],
        'movie_id': movie_id,
        'imdb_id': watchlist_item['imdb_id'],
        'status': new_status,
    }],
        'watchlists')


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


def get_torrents_for_imdb_id(idd):
    r = requests.get(
        url=API_URL,
        params={
            'username': USER,
            'passkey': PASSKEY,
            'action': 'search-torrents',
            'type': 'imdb',
            'query': convert_imdb_id(idd),
            'category': ','.join([str(MOVIE_HDRO), str(MOVIE_4K)])
        },
    )
    # Remove 4K if they're not Remux
    response = []
    for x in r.json():
        if x['category'] == MOVIE_4K:
            if 'Remux' in x['name']:
                x['resolution'] = get_torr_quality(x['name'])
                response.append(x)
        else:
            x['resolution'] = get_torr_quality(x['name'])
            response.append(x)
    return response


def get_movie_from_all_databases(imdb_id):
    conn, cursor = connect_mysql()
    # Check if it's in my_movies:
    my_item = check_one_in_my_movies(imdb_id, cursor)
    if not my_item:
        my_item = dict()
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
    if my_item:
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


def get_watchlist_new(cursor=None):
    if not cursor:
        conn, cursor = connect_mysql()
    q = f"SELECT * FROM watchlists WHERE status = 'new'"
    cursor.execute(q)
    return cursor.fetchall()


if __name__ == '__main__':
    from pprint import pprint

    # print(make_trailer(link))
    # pprint(get_telegram_users())
    pprint(get_excluded_resolutions(1571222, 1700079840))
