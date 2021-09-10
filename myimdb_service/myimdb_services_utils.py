import os

from utils import setup_logger, connect_plex, get_plex_users, get_user_movies, check_against_user_watchlist, \
    get_user_watchlist, deconvert_imdb_id

PLEX_ADMIN_EMAILS = os.getenv('PLEX_ADMIN_EMAILS').replace('"', '').replace(' ', '')
if ',' in PLEX_ADMIN_EMAILS:
    PLEX_ADMIN_EMAILS = PLEX_ADMIN_EMAILS.split(', ')
else:
    PLEX_ADMIN_EMAILS = [PLEX_ADMIN_EMAILS]

logger = setup_logger("DbServicesUtils")


def get_my_movies(email):
    movies = get_user_movies(email)
    if movies:
        return [x['imdb_id'] for x in movies]


def get_watchlist_intersections_ids(user_imdb_id, movies):
    user_watchlist = get_user_watchlist(user_imdb_id)
    if user_watchlist:
        intersections = [x['imdb_id'] for x in user_watchlist if x['imdb_id'] in movies]
        if intersections:
            return intersections


def get_user_watched_movies(email, account=None, plex=None):
    def return_movie_id(movie):
        guids = [x.id for x in movie.guids]
        for idd in guids:
            if 'imdb' in idd:
                return {'imdb_id': int(deconvert_imdb_id(idd.split('//tt')[-1])), 'seen_date': movie.lastViewedAt}
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
            logger.warning("Email not in users, ignore if he's admin.")
            return None
    if email == PLEX_ADMIN_EMAILS[0]:
        pass
    else:
        try:
            user = [x.name for x in plex.systemAccounts() if x.name == email][0]
            plex = plex.switchUser(user)
        except IndexError:
            logger.error('Email not in users or admins.')
            return None

    movies = plex.library.section('Movies')
    movies = movies.search(unwatched=False)
    ids = [return_movie_id(movie) for movie in movies]
    return [x for x in ids if x]
