# -*- coding: utf-8 -*-
import os
import urllib.parse
from itertools import groupby

import PTN

from jinja2 import Environment, FileSystemLoader
from utils import check_against_user_movies, insert_many, Torrent
from utils import get_my_imdb_users
from utils import get_torr_quality
from utils import setup_logger

XML_TRNT_PATH = os.getenv('XML_TRNT_PATH')
TEMPLATE_PATH = os.getenv('TEMPLATE_PATH')
MOVIE_TEMPLATE_PATH = os.getenv('MOVIE_TEMPLATE_PATH')
TRNT_TEMPLATE_PATH = os.getenv('TRNT_TEMPLATE_PATH')
EMAIL_USER = os.getenv('EMAIL_USER')
EMAIL_PASS = os.getenv('EMAIL_PASS')
EMAIL_HOSTNAME = os.getenv('EMAIL_HOSTNAME')
PLEX_SERVER_NAME = os.getenv('PLEX_SERVER_NAME')

TORR_KEEP_TIME = int(os.getenv('TORR_KEEP_TIME')) if os.getenv('TORR_KEEP_TIME') else 60
TORR_HOST = os.getenv('TORR_HOST')
TORR_PORT = int(os.getenv('TORR_PORT')) if os.getenv('TORR_PORT') else 9091
TRANSMISSION_USER = os.getenv('TRANSMISSION_USER')
TRANSMISSION_PASS = os.getenv('TRANSMISSION_PASS')
TORR_API_HOST = os.getenv('TORR_API_HOST')
TORR_API_PORT = os.getenv('TORR_API_PORT')
TORR_API_PATH = os.getenv('TORR_API_PATH')
TORR_SEED_FOLDER = os.getenv('TORR_SEED_FOLDER')
TORR_DOWNLOAD_FOLDER = os.getenv('TORR_DOWNLOAD_FOLDER')

logger = setup_logger('EmailSender')


def generate_movie_table(mprm, tprm):
    """
    Render a single movie card with its torrent rows using Jinja2.
    Preserves the original function signature and returns HTML string.
    """
    env = get_template_env()
    template_name = os.path.basename(MOVIE_TEMPLATE_PATH) if MOVIE_TEMPLATE_PATH else '_movie.html'
    template = env.get_template(template_name)
    ctx = build_movie_context(mprm, tprm)
    return template.render(**ctx) + '\n'


def get_template_env():
    """
    Initialize Jinja2 environment to load templates from the 'views' directory.
    Uses TEMPLATE_PATH env var to infer base dir, falls back to local views.
    """
    base_dir = os.path.join(os.path.dirname(__file__), os.path.dirname(TEMPLATE_PATH)) if TEMPLATE_PATH else os.path.join(os.path.dirname(__file__), 'views')
    return Environment(loader=FileSystemLoader(base_dir), autoescape=False, trim_blocks=True, lstrip_blocks=True)

def build_movie_context(mprm, tprm):
    """
    Build the Jinja2 context expected by _movie.html and _torrent.html.
    Converts 'mprm_*' placeholders and computes 'class_*' badge classes.
    Also converts tprm dict to a 'torrents' list for template iteration.
    """
    score_list = ('imdb_score', 'score', 'rott_score', 'meta_score', 'my_imdb_score')
    genre_bad_list = ('Horror', 'Animation')
    country_bad_list = ('India', 'Bahasa indonesia', 'China')

    def safe_value(v):
        return None if v in ('None', False, 'N/A', None) else str(v)

    ctx = {}

    # Map movie parameters to mprm_* variables with formatting
    for key, raw in (mprm or {}).items():
        val = safe_value(raw)

        # Highlight disliked genres/countries
        if key == 'genre' and val:
            for g in genre_bad_list:
                if g.lower() in val.lower():
                    val = val.replace(g, f'<span style="color: #ff0000;"><strong>{g}</strong></span>')
        if key in ('country', 'countries') and val:
            for c in country_bad_list:
                if c.lower() in val.lower():
                    val = val.replace(c, f'<span style="color: #ff0000;"><strong>{c}</strong></span>')

        # Trailer link
        if key == 'trailer':
            val = f'<a href="{val}" target="_blank">WATCH TRAILER</a>' if val else ''

        # Empty for personal score and seen_date
        if key in ('my_imdb_score', 'seen_date') and not val:
            val = ''

        ctx[f'mprm_{key}'] = val if val is not None else ('---' if key not in ('my_imdb_score', 'seen_date', 'trailer') else '')

    # Ensure compatibility variants
    if 'mprm_countries' not in ctx and 'mprm_country' in ctx:
        ctx['mprm_countries'] = ctx['mprm_country']
    if 'mprm_directors' not in ctx and 'mprm_director' in ctx:
        ctx['mprm_directors'] = ctx['mprm_director']

    # Compute classes for score badges
    for key in score_list:
        val = ctx.get(f'mprm_{key}')
        ctx[f'class_{key}'] = get_key_class(key, val) if val not in (None, '', '---') else ''

    # Build torrent rows list
    torrents = []
    for _, tr in (tprm or {}).items():
        tr_resolution = tr.get('resolution') or (f"{get_torr_quality(tr.get('name'))}p" if tr.get('name') else None)
        torrents.append({
            'trnt_trend': tr.get('trend', ''),
            'trnt_resolution': str(tr_resolution) if tr_resolution else '',
            'trnt_sizeGb': tr.get('size'),
            'trnt_freeleech': True if tr.get('freeleech') else False,
            'trnt_torr_link_seed': tr.get('torr_link_seed'),
            'trnt_torr_link_download': tr.get('torr_link_download'),
        })
    ctx['torrents'] = torrents

    return ctx


def get_key_class(key, value):
    if key == 'imdb_score' or key == 'score':
        if float(value) < 5:
            new_value = 'neg'
        elif float(value) >= 7:
            new_value = 'poz'
        else:
            new_value = 'std'

    elif key == 'rott_score':
        if int(float(value)) < 60:
            new_value = 'neg'
        elif int(float(value)) >= 75:
            new_value = 'poz'
        else:
            new_value = 'std'

    elif key == 'meta_score':
        if int(float(value)) < 40:
            new_value = 'neg'
        elif int(float(value)) > 60:
            new_value = 'poz'
        else:
            new_value = 'std'

    elif key == 'my_imdb_score':
        new_value = 'prs'

    else:
        new_value = 'std'

    return new_value


def generate_trnt_table(tprm):
    """
    Deprecated: torrent rows are now rendered by Jinja2 in the movie template.
    Kept for backward compatibility; returns empty string.
    """
    return ''


def generate_email_html(list_new, list_trnt):
    """
    Render the base email wrapper using Jinja2, injecting pre-rendered HTML
    for 'list_new' and 'list_trnt'. Returns empty string if both are empty.
    """
    if not list_new and not list_trnt:
        return ''
    env = get_template_env()
    template_name = os.path.basename(TEMPLATE_PATH) if TEMPLATE_PATH else 'email_filelist.html'
    template = env.get_template(template_name)
    return template.render(list_new=list_new or '', list_trnt=list_trnt or '')


def send_email(tFromName, tFromEmail, tToList, tSubject, tBody, lFiles, tSMTP, tUser, tPass):
    try:
        import smtplib
        from email.utils import formatdate
        from email.mime.text import MIMEText
        from email.mime.image import MIMEImage
        from email.mime.multipart import MIMEMultipart
        from email.mime.application import MIMEApplication

        msg = MIMEMultipart()
        msg['From'] = '{0} <{1}>'.format(tFromName, tFromEmail)
        msg['To'] = tFromEmail
        msg['Date'] = formatdate(localtime=True)
        msg['Reply-to'] = tFromEmail
        msg['Subject'] = tSubject
        msg.attach(MIMEText(tBody.encode('utf-8'), 'html', 'UTF-8'))

        for f in lFiles or []:
            with open(f, "rb") as fil:
                ext = f.split('.')[-1:]
                attachedfile = MIMEApplication(fil.read(), _subtype=ext)
                attachedfile.add_header('content-disposition', 'attachment', filename=os.path.basename(f))
            msg.attach(attachedfile)

        server = smtplib.SMTP(tSMTP, 587)
        server.ehlo()
        server.starttls()
        server.login(tUser, tPass)
        server.sendmail(tFromEmail, tToList, msg.as_string())
        server.quit()

    except Exception as vErr:
        logger.error('[send_email] Nu am putut trimite email: ', str(vErr))


def prepare_item_for_email(item, user_telegram_id):
    # Add seen type keys
    if item['in_my_movies']:
        item['seen_type'] = 1  # new movie
    else:
        item['seen_type'] = 0  # we have this movie but here's a new torrent for it

    # Convert some keys

    item['size'] = "%.1f" % (float(item['size']) / 1000000000) if 'size' in item.keys() else None
    item['year'] = item['startYear'] if 'startYear' in item.keys() else None
    item['genre'] = item['genres'] if 'genres' in item.keys() else None
    item['runtime'] = item['runtimeMinutes'] if 'runtimeMinutes' in item.keys() else None
    item['imdb_score'] = item['averageRating'] if 'averageRating' in item.keys() else None
    item['score'] = item['tmdb_score'] if 'tmdb_score' in item.keys() else None
    item['my_imdb_score'] = item['my_score'] if 'my_score' in item.keys() else None
    item['seen_date'] = item['seen_date'] if 'seen_date' in item.keys() else None
    item['resolution'] = str(get_torr_quality(item['name'])) + 'p' if 'name' in item.keys() else None
    item['trend'] = ''
    item['id'] = str(item['id'])
    item['freeleech'] = True if item['freeleech'] == 1 else False
    item['trailer'] = item['trailer_link']

    try:
        del item['imdb']
    except:
        pass

    # Add keys for torrent API and generate AES hash for each torrent
    item['torr_link_seed'], item['torr_link_download'] = generate_torr_links(item, user_telegram_id)

    return item


def check_in_my_movies(new_movies, email):
    """
    checks if passed new movies are already in database.
    :param new_movies: dict, returned from FL API
    :return: filtered dict
    """

    def get_intersections(new, old):
        """
        Makes intersections with database,
        adds already_in_db and better_quality parameters.
        :param new:
        :param old:
        :return:
        """
        old_movies_ids = [x['imdb_id'] for x in old]
        for new_m in new:
            if new_m['imdb_id'] in old_movies_ids:
                new_m['in_my_movies'] = True
            else:
                new_m['in_my_movies'] = False
        return new

    already_in_db = check_against_user_movies(new_movies, email)
    new = get_intersections(new_movies, already_in_db)
    return new


def generate_torr_links(item, user_telegram_id, cypher=None):
    def compose_link(pkg):
        # Cypher alternative
        # pkg = cypher.encrypt(json.dumps(pkg))
        # No Cypher alternative
        pkg = urllib.parse.urlencode(pkg)
        return f"http://{TORR_API_HOST}:{TORR_API_PORT}{TORR_API_PATH}?{pkg}"

    seed = {
        'torr_id': item['id'],
        'imdb_id': item['imdb_id'],
        'resolution': get_torr_quality(item['name']),
        'folder': TORR_SEED_FOLDER,
        'requested_by': user_telegram_id,
    }
    download = {
        'torr_id': item['id'],
        'imdb_id': item['imdb_id'],
        'resolution': get_torr_quality(item['name']),
        'folder': TORR_DOWNLOAD_FOLDER,
        'requested_by': user_telegram_id,
    }
    return compose_link(seed), compose_link(download)


def do_email(items):
    if items:
        logger.info("Starting emailing routine")
        users = [x for x in get_my_imdb_users() if x['email_newsletters']]
        for user in users:
            # Filter for each user, with what they've seen
            user_items = check_in_my_movies(items, user['email'])
            if user_items:
                user_items = [prepare_item_for_email(item, user['telegram_chat_id']) for item in user_items]
                # Group by imdb_id
                # Sort
                for item in user_items:
                    try:
                        item['imdb_id'] = int(item['imdb_id'])
                    except TypeError:
                        pass
                user_items.sort(key=lambda x: x['imdb_id'])

                new_items = []
                for k, v in groupby(user_items, key=lambda x: x['imdb_id']):
                    new_items.append({
                        'imdb_id': k,
                        'torrents': list(v)
                    })

                list_new = ''
                list_trnt = ''

                for nr, item in enumerate(new_items):
                    if item['torrents'][0]['seen_type'] == 0:
                        all_movie = {'crt': '{0}'.format(nr + 1), 'id_imdb': '{0}'.format(item['imdb_id']),
                                     'bck_color': 'F4CCCC'}
                        all_trnt = {}
                        for trnt in item['torrents']:
                            all_movie = {**trnt, **all_movie}

                            one_trnt = trnt
                            all_trnt[trnt['id']] = one_trnt
                        list_new += generate_movie_table(all_movie, all_trnt)

                    elif item['torrents'][0]['seen_type'] == 1:  # FFF2CC
                        all_movie = {'crt': '{0}'.format(nr + 1), 'id_imdb': '{0}'.format(item['imdb_id']),
                                     'bck_color': 'FFF2CC'}
                        all_trnt = {}
                        for trnt in item['torrents']:
                            all_movie = {**trnt, **all_movie}

                            one_trnt = trnt
                            all_trnt[trnt['id']] = one_trnt

                        list_trnt += generate_movie_table(all_movie, all_trnt)

                email_body = generate_email_html(list_new, list_trnt)

                if len(new_items) == 1:
                    mail_subject = 'Film nou pe FileList'
                elif len(new_items) > 1:
                    mail_subject = '{0} filme noi pe FileList'.format(len(new_items))
                else:
                    mail_subject = 'Nou pe FileList'

                if email_body:
                    logger.info('Sending email')
                    send_email(PLEX_SERVER_NAME, EMAIL_USER, [user['email']], mail_subject, email_body, '',
                               EMAIL_HOSTNAME, EMAIL_USER, EMAIL_PASS)

                # Insert into torrents database
                to_insert = [{'torr_id': x['id'],
                              'imdb_id': x['imdb_id'],
                              'status': 'user notified (email)',
                              'resolution': int(PTN.parse(x['name'])['resolution'][:-1]),
                              'torr_hash': None,
                              'requested_by_id': user['telegram_chat_id']
                              }
                             for x in user_items]
                insert_many(to_insert, Torrent)
        return
    logger.info('Nothing left to send')

