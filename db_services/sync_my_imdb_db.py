import datetime
import time

import requests
from utils import logger, deconvert_imdb_id, update_many
from bs4 import BeautifulSoup
from db_tools import get_my_imdb_users, get_my_movies
from plex_utils import get_user_watched_movies
import re


def sync_my_imdb():
    logger.info("Getting users")
    users = get_my_imdb_users()
    for user in users:
        pass
        # Get movies already in DB
        already_in_my_movies = get_my_movies(user['email'])
        # Sync IMDB data
        if user['imdb_id']:
            imdb_data = get_my_imdb(user['imdb_id'])
            imdb_data = [{'imdb_id': deconvert_imdb_id(key), 'my_score': val['rating'], 'seen_date': val['date'],
                          'user': user['email']} for key, val in imdb_data.items() if key not in already_in_my_movies]
            update_many(imdb_data, 'my_movies')

        already_in_my_movies = get_my_movies(user['email'])
        # Sync PLEX data
        plex_data = get_user_watched_movies(user['email'])
        plex_data = [x for x in plex_data if x['imdb_id'] not in already_in_my_movies]
        for item in plex_data:
            item['user'] = user['email']
        # update_many(plex_data, 'my_movies')


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
    # TODO, fking regex + js injection
    try:
        url = 'https://www.imdb.com/user/ur{0}/watchlist'.format(profile_id)
        print(url)
        soup_imdb = BeautifulSoup(requests.get(url).text, 'html.parser')
        html_content = soup_imdb.prettify()
        Html_file = open("example.html", "w")
        Html_file.write(html_content)
        Html_file.close()
        pages = 10

        results = []
        for page in range(pages + 1):
            html_content = soup_imdb.prettify()
            print(re.findall("[IMDbReactInitialState.push(].*[);]", html_content))
            ids = soup_imdb.findAll('div', {'class': 'lister-item-image'})
            print(ids)
            try:
                last_page = False
                next_url = soup_imdb.find('a', {'class': 'flat-button lister-page-next next-page'})['href']
            except:
                last_page = True
            for x in ids:
                imdb_id = x['data-tconst']
                results.append(imdb_id)
            if not last_page:
                next_url = 'https://www.imdb.com{0}'.format(next_url)
                soup_imdb = BeautifulSoup(requests.get(next_url).text, 'html.parser')

        return results

    except Exception as e:
        raise(e)
        logger.error(f"Could not fetch MyIMDB for user {profile_id}, error: {e}")
        return None


if __name__ == '__main__':
    from pprint import pprint
    # x = get_my_imdb(30152272)
    sync_my_imdb()
