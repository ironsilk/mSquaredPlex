# -*- coding: utf-8 -*-
import os
import urllib.parse
from itertools import groupby

import PTN

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

TORR_KEEP_TIME = int(os.getenv('TORR_KEEP_TIME'))
TORR_HOST = os.getenv('TORR_HOST')
TORR_PORT = int(os.getenv('TORR_PORT'))
TORR_USER = os.getenv('TORR_USER')
TORR_PASS = os.getenv('TORR_PASS')
TORR_API_HOST = os.getenv('TORR_API_HOST')
TORR_API_PORT = os.getenv('TORR_API_PORT')
TORR_API_PATH = os.getenv('TORR_API_PATH')
TORR_SEED_FOLDER = os.getenv('TORR_SEED_FOLDER')
TORR_DOWNLOAD_FOLDER = os.getenv('TORR_DOWNLOAD_FOLDER')

logger = setup_logger('EmailSender')


def generate_movie_table(mprm, tprm):
    template_file = open(MOVIE_TEMPLATE_PATH, 'r')
    template = template_file.read()
    template_file.close()

    for key, value in mprm.items():
        if key in template:
            template = template_replace(template, key, value)

    template = template.replace('trnt_tbody', generate_trnt_table(tprm))

    return template + '\n'


def template_replace(template, key, value):
    score_list = ('imdb_score', 'score', 'rott_score', 'meta_score', 'my_imdb_score')
    genre_bad_list = ('Horror', 'Animation')
    country_bad_list = ('India', 'Bahasa indonesia', 'China')

    if value != 'None' and value != False and value != 'N/A' and value is not None:
        value = str(value)
        if key in score_list:
            class_value = get_key_class(key, value)
            template = template.replace('mprm_{0}'.format(key), value)
            template = template.replace('class_{0}'.format(key), class_value)

        elif key == 'genre':
            for genre in genre_bad_list:
                if genre.lower() in value.lower():
                    value = value.replace(genre,
                                          '<span style="color: #ff0000;"><strong>{0}</strong></span>'.format(genre))

        elif key == 'country':
            for country in country_bad_list:
                if country.lower() in value.lower():
                    value = value.replace(country,
                                          '<span style="color: #ff0000;"><strong>{0}</strong></span>'.format(
                                              country))

        elif key == 'trailer':
            value = '<a href="{0}" target="_blank">WATCH TRAILER</a>'.format(value)
            template = template.replace('mprm_{0}'.format(key), value)

        template = template.replace('mprm_{0}'.format(key), value)

    else:

        if key == 'my_imdb_score' or key == 'seen_date':
            template = template.replace('mprm_{0}'.format(key), '')
            template = template.replace('class_{0}'.format(key), '')

        elif key == 'trailer':
            template = template.replace('mprm_{0}'.format(key), '')

        else:
            template = template.replace('mprm_{0}'.format(key), '---')
            template = template.replace('class_{0}'.format(key), '')

    return template


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
    template_file = open(TRNT_TEMPLATE_PATH, 'r')
    template = template_file.read()
    template_file.close()

    trnt_tbody = template
    index = 0

    for key, value in tprm.items():
        if isinstance(value, dict):
            for key2, value2 in value.items():
                trnt_tbody = trnt_tbody.replace('trnt_id_filelist', key)
                if value2 == True:
                    trnt_tbody = trnt_tbody.replace('trnt_{0}'.format(key2),
                                                    '<img src="https://filelist.io/styles/images/tags/freeleech.png" alt="freeleech" />')
                elif value2 != 'None' and value2 != False and value2 != 'N/A' and value2 is not None:
                    value2 = str(value2)
                    trnt_tbody = trnt_tbody.replace('trnt_{0}'.format(key2), value2)

            # replace all param without values with dash/'---'
            for key2, value2 in value.items():
                trnt_tbody = trnt_tbody.replace('trnt_{0}'.format(key2), '')

            index += 1
            if index < len(tprm):
                trnt_tbody += template
        else:
            if key in template:
                trnt_tbody = trnt_tbody.replace('trnt_id_filelist', key)
                if value == True:
                    # trnt_tbody = trnt_tbody.replace('trnt_{0}'.format(key), 'freeleech')
                    trnt_tbody = trnt_tbody.replace('trnt_{0}'.format(key2),
                                                    '<img src="https://filelist.io/styles/images/tags/freeleech.png" alt="freeleech" />')
                elif value != 'None' and value != False and value != 'N/A' and value is not None:
                    value = str(value)
                    trnt_tbody = template.replace('trnt_{0}'.format(key), value)

    return trnt_tbody


def generate_email_html(list_new, list_trnt):
    template_file = open(TEMPLATE_PATH, 'r')
    template = template_file.read()
    template_file.close()

    email_body = template

    if not list_new and not list_trnt:
        email_body = ''
    else:
        if list_new != '':
            email_body = email_body.replace('list_new', list_new)
        else:
            email_body = email_body.replace('list_new', '')

        if list_trnt != '':
            email_body = email_body.replace('list_trnt', list_trnt)
        else:
            email_body = email_body.replace('list_trnt', '')

    return email_body


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
        logger.debug('[send_email] Nu am putut trimite email: ', str(vErr))


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
        users = [x for x in get_my_imdb_users() if x['email_newsletters'] == 1]
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

