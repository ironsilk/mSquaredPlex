import os

import PTN
import requests
from telegram.ext import CallbackContext

from utils import update_many, convert_imdb_id, get_torr_quality, get_new_watchlist_items, \
    get_from_watchlist_by_user_telegram_id_and_imdb
from utils import get_my_imdb_users, setup_logger, Watchlist

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
    watchlist_items = get_new_watchlist_items()
    if watchlist_items:
        for item in watchlist_items:
            torrents = get_torrents_for_imdb_id(item['imdb_id'])
            torrents = sorted(torrents, key=lambda k: k['size'])
            if item['excluded_torrents']:
                torrents = [x for x in torrents if str(x['id']) not in item['excluded_torrents']]
            if item['is_downloaded']:
                torrents = [x for x in torrents if str(x['resolution']) != item['is_downloaded']]

            if torrents:
                message = f"Hi there! WATCHLIST ALERT!\n"\
                          f"🎞️ {PTN.parse(torrents[0]['name'])['title']}\n"\
                          f"has {len(torrents)} download candidates\n"\
                          f"📥 /WatchMatch_{item['imdb_id']} (download)\n\n"\
                          f"❌ /UnWatchMatch_{item['imdb_id']} (forget movie)"
                if item['is_downloaded']:
                    message += f"\n🚨 Movie aleady exists in PLEX, quality: {item['is_downloaded']}"
                context.bot.send_message(chat_id=item['user_id'], text=message)
                update_watchlist_item_status(item['imdb_id'], item['user_id'], 'notification sent')


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
    watchlist_item = get_from_watchlist_by_user_telegram_id_and_imdb(movie_id, tg_id)
    update_many([{
        'id': watchlist_item['id'],
        'imdb_id': movie_id,
        'user_id': tg_id,
        'status': new_status,
    }],
        Watchlist, Watchlist.id)

