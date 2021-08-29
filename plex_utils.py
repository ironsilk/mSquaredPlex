from plexapi.server import PlexServer
from settings import PLEX_HOST, PLEX_TOKEN, PLEX_SERVER_NAME, PLEX_ADMIN_EMAILS
from settings import setup_logger

# How to get the plex token:
# https://digiex.net/threads/plex-guide-step-by-step-getting-plex-token.15402/
baseurl = 'http://192.168.1.99:32400'
token = '4VzQJvzMYEviPx3iWGkT'

logger = setup_logger("PlexServices")


def connect_plex():
    # Server
    plex = PlexServer(PLEX_HOST, PLEX_TOKEN)
    # Account
    account = plex.myPlexAccount()
    return account, plex


def invite_friend(email, account=None, plex=None):
    if not account:
        account, plex = connect_plex()
    try:
        account.inviteFriend(email, plex)
    except Exception as e:
        logger.error(e)
        return False
    return True


def get_plex_users(account=None, plex=None):
    if not account:
        account, plex = connect_plex()
    return account.users()


def get_plex_emails():
    # Admins
    emails = PLEX_ADMIN_EMAILS.copy()
    # Friends
    users = get_plex_users()
    users = [x.email for x in users if x.email and x.email not in emails]

    return emails + users


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



# TODO maybe add method here to sync movie rating


if __name__ == '__main__':
    from pprint import pprint
    pprint(get_plex_emails())
