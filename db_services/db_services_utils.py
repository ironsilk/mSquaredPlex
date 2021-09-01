import datetime
import os

from utils import setup_logger, connect_mysql, connect_plex, get_plex_users

PLEX_ADMIN_EMAILS = os.getenv('PLEX_ADMIN_EMAILS')
if ',' in PLEX_ADMIN_EMAILS:
    PLEX_ADMIN_EMAILS = PLEX_ADMIN_EMAILS.split(', ')
else:
    PLEX_ADMIN_EMAILS = [PLEX_ADMIN_EMAILS]

logger = setup_logger("DbServicesUtils")


def get_my_movies(email, cursor=None):
    if not cursor:
        conn, cursor = connect_mysql()
    q = f"SELECT `imdb_id` FROM my_movies where user = '{email}'"
    cursor.execute(q)
    return [x['imdb_id'] for x in cursor.fetchall()]


def get_watchlist_intersections(user_imdb_id, watchlist, cursor=None):
    if not cursor:
        conn, cursor = connect_mysql()
    values = "','".join([str(x) for x in watchlist])
    q = f"SELECT movie_id FROM watchlists WHERE movie_id IN ('{values}') AND imdb_id = {user_imdb_id}"
    cursor.execute(q)
    return [x['movie_id'] for x in cursor.fetchall()]


def remove_from_watchlist(except_these_movie_ids, user_imdb_id, cursor=None):
    if not cursor:
        conn, cursor = connect_mysql()
    values = "', '".join([str(x) for x in except_these_movie_ids])
    q = f"SELECT id FROM watchlists WHERE movie_id NOT IN ('{values}') AND imdb_id = {user_imdb_id}"
    cursor.execute(q)
    to_delete = [x['id'] for x in cursor.fetchall()]
    if to_delete:
        values = "', '".join([str(x) for x in to_delete])
        q = f"DELETE FROM watchlists where id IN ('{values}')"
        cursor.execute(q)
    return


def get_user_watched_movies(email, account=None, plex=None):
    def return_movie_id(movie):
        guids = [x.id for x in movie.guids]
        for idd in guids:
            if 'imdb' in idd:
                return {'imdb_id': idd.split('//tt')[-1], 'seen_date': movie.lastViewedAt}
        return None

    if not account:
        account, plex = connect_plex()

    if email not in PLEX_ADMIN_EMAILS:
        # Get users
        users = get_plex_users(account, plex)
        try:
            user = [x for x in users if x.email == email][0]
            plex = plex.switchUser(user.id)
        except IndexError:
            logger.error('Email not in users')
            return None
    elif email == PLEX_ADMIN_EMAILS[0]:
        pass
    else:
        try:
            user = [x.name for x in plex.systemAccounts() if x.name == email][0]
            plex = plex.switchUser(user)
        except IndexError:
            logger.error('Email not in users')
            return None

    movies = plex.library.section('Movies')
    movies = movies.search(unwatched=False)
    ids = [return_movie_id(movie) for movie in movies]
    return [x for x in ids if x]