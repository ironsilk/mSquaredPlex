import datetime
import os
import re
import time

import pandas as pd
import requests
from bs4 import BeautifulSoup
from plexapi.exceptions import Unauthorized

from bot_rate_title import run_ratetitle_dog
from bot_watchlist import run_watchlist_dog
from myimdb_services_utils import get_my_movies, get_watchlist_intersections_ids, get_user_watched_movies
from utils import deconvert_imdb_id, update_many, setup_logger, check_database, remove_from_watchlist_except, Movie, \
    insert_many
from utils import get_my_imdb_users, Watchlist, get_user_watchlist, check_one_against_torrents_by_imdb
from sync_torrents import sync_torrent_statuses

SYNC_INTERVAL = int(os.getenv('SYNC_INTERVAL')) if os.getenv('SYNC_INTERVAL') else 1

logger = setup_logger("MyIMDBsync")


def sync_my_imdb():
    logger.info("Getting users")
    users = get_my_imdb_users()
    for user in users:
        logger.info(f"Syncing data for {user['email']}")
        # Get movies already in DB
        already_in_my_movies = get_my_movies(user)
        if not already_in_my_movies:
            already_in_my_movies = []
        # Sync IMDB ratings
        if user['imdb_id']:
            imdb_data = get_my_imdb(user['imdb_id'])
            imdb_data = [{'imdb_id': deconvert_imdb_id(key), 'my_score': val['rating'], 'seen_date': val['date'],
                          'user_id': user['telegram_chat_id'], 'rating_status': 'IMDB rated'}
                         for key, val in imdb_data.items() if int(deconvert_imdb_id(key)) not in already_in_my_movies]
            insert_many(imdb_data, Movie)

        already_in_my_movies = get_my_movies(user) or []
        # Sync PLEX views and ratings
        try:
            plex_data = get_user_watched_movies(user['email'])
        except Unauthorized:
            logger.error(f"Error retrieving PLEX data for user {user['email']}, unauthorised")
            plex_data = None
        if plex_data:
            plex_data = [x for x in plex_data if x['imdb_id'] not in already_in_my_movies]
            for item in plex_data:
                item['user_id'] = user['telegram_chat_id']
                item['rating_status'] = 'bulk unrated'
            insert_many(plex_data, Movie)
        # Sync IMDB watchlist
        if user['scan_watchlist'] == 1:
            sync_watchlist(user)
        logger.info("Done.")


def get_my_imdb(profile_id):
    try:
        url = 'https://www.imdb.com/user/ur{0}/ratings'.format(profile_id)
        soup_imdb = BeautifulSoup(requests.get(url).text, 'html.parser')
        titles = int(soup_imdb.find('div', class_='lister-list-length').find('span',
                                                                             id='lister-header-current-size').get_text().replace(
            ',', ''))
        pages = int(titles / 100) + 1

        results = {}
        for page in range(pages + 1):
            ids = soup_imdb.findAll('div', {'class': 'lister-item-image ribbonize'})
            ratings = soup_imdb.findAll('div', {'class': 'ipl-rating-star ipl-rating-star--other-user small'})
            dates = []

            for y in soup_imdb.findAll('p', {'class': 'text-muted'}):
                if str(y)[:30] == '<p class="text-muted">Rated on':
                    date = re.search('%s(.*)%s' % ('Rated on ', '</p>'), str(y)).group(1)
                    dates.append(date)
            try:
                last_page = False
                next_url = soup_imdb.find('a', {'class': 'flat-button lister-page-next next-page'})['href']
            except:
                last_page = True
            for x, y, z in zip(ids, ratings, dates):
                imdb_id = x['data-tconst']
                rating = int(y.get_text())
                date = datetime.datetime.strptime(z, '%d %b %Y')
                date = date.strftime('%Y-%m-%d')
                results.update({imdb_id: {'rating': rating, 'date': date}})
            if not last_page:
                next_url = 'https://www.imdb.com{0}'.format(next_url)
                soup_imdb = BeautifulSoup(requests.get(next_url).text, 'html.parser')

        return results

    except Exception as e:
        logger.error(f"Could not fetch MyIMDB for user {profile_id}, error: {e}")
        return None


def get_my_watchlist(profile_id):
    try:
        url = f'https://www.imdb.com/user/ur{profile_id}/watchlist'
        soup_imdb = BeautifulSoup(requests.get(url).text, 'html.parser')
        listId = soup_imdb.find("meta", property="pageId")['content']
        url = f"https://www.imdb.com/list/{listId}/export"
        df = pd.read_csv(url)
        # Return only movies
        return df.loc[df['Title Type'] == 'movie']['Const'].tolist()
    except Exception as e:
        logger.error(f"Can't fetch IMDB Watchlist for user {profile_id}, error: {e}")
        return None


def sync_watchlist(user):
    logger.info(f"Syncing watchlist for user {user['email']}")
    try:
        # IMDB watchlist
        imdb_watchlist = get_my_watchlist(user['imdb_id'])
        imdb_watchlist = [int(deconvert_imdb_id(x)) for x in imdb_watchlist]
        # My DB watchlist which are also in IMDB
        already_processed = get_watchlist_intersections_ids(user['imdb_id'], imdb_watchlist)
        # Add new items added to IMDB watchlist
        if already_processed:
            new_watchlist = [x for x in imdb_watchlist if x not in already_processed]
        else:
            new_watchlist = imdb_watchlist
        to_upload = [{
            'imdb_id': x,
            'user_id': user['telegram_chat_id'],
            'status': 'new',
        } for x in new_watchlist]
        if to_upload:
            insert_many(to_upload, Watchlist)
        # Remove from DB watchlist those movies which are no longer in IMDB watchlist
        remove_from_watchlist_except(imdb_watchlist, user['imdb_id'])

        # Update watchlist item status if we find a torrent already downloaded
        watchlist = get_user_watchlist(user['imdb_id'])
        if watchlist:
            for item in watchlist:
                is_in_my_torrents = check_one_against_torrents_by_imdb(item['imdb_id'])
                if is_in_my_torrents:
                    item['is_downloaded'] = is_in_my_torrents[0]['resolution']
                    update_many([item], Watchlist, Watchlist.id)
    except Exception as e:
        logger.error(f"Watchlist sync for user {user['email']} failed. Error: {e}")
    logger.info("Done.")


def run_sync():
    """
    Sync IMDB ratings given by user
    Sync IMDB user watchlist
    Sync PLEX user activity / ratings
    """
    while True:
        # Sync the services
        sync_my_imdb()
        # Sync torrent statuses
        sync_torrent_statuses()
        # Send rating notifications from bot
        run_ratetitle_dog()
        # Send watchlist notifications from bot
        run_watchlist_dog()
        logger.info(f"Sleeping {SYNC_INTERVAL} minutes...")
        time.sleep(SYNC_INTERVAL * 60)


if __name__ == '__main__':
    check_database()
    run_sync()
