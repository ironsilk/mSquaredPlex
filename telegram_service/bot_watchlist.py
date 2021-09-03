import os

import PTN
import requests
from telegram.ext import CallbackContext

from telegram_service.bot_utils import get_watchlist_item
from utils import connect_mysql, update_many, convert_imdb_id, get_torr_quality
from utils import get_my_imdb_users, setup_logger

NO_POSTER_PATH = os.getenv('NO_POSTER_PATH')
API_URL = os.getenv('API_URL')
USER = os.getenv('USER')
PASSKEY = os.getenv('PASSKEY')

MOVIE_HDRO = os.getenv('MOVIE_HDRO')
MOVIE_4K = os.getenv('MOVIE_4K')


logger = setup_logger("BotWatchlist")


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


def get_watchlist_new(cursor=None):
    if not cursor:
        conn, cursor = connect_mysql()
    q = f"SELECT * FROM watchlists WHERE status = 'new'"
    cursor.execute(q)
    return cursor.fetchall()


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


def update_watchlist_item_status(movie_id, tg_id, new_status):
    watchlist_item = get_watchlist_item(movie_id, tg_id)
    update_many([{
        'id': watchlist_item['id'],
        'movie_id': movie_id,
        'imdb_id': watchlist_item['imdb_id'],
        'status': new_status,
    }],
        'watchlists')

