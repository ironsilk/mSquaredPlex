# -*- coding: utf-8 -*-
import datetime
import json
import os
import xml.etree.ElementTree as ET
from xml.dom import minidom
from xml.etree.ElementTree import SubElement

import PTN

from utils import OMDB, check_against_user_movies
from utils import TMDB
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

# seen_type:
'''
0 = new movie
1 = new torrent
2 = seen or dw movie
'''


class Mtls:

    def __init__(self):
        self.description = 'my tools'

    def send_email(self, tFromName, tFromEmail, tToList, tSubject, tBody, lFiles, tSMTP, tUser, tPass):
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

    def xml_pritify(self, xml_file_path):
        try:
            tree = ET.parse(xml_file_path)
        except Exception as e:
            logger.debug('fisier XML corupt: ' + str(e))

        root = tree.getroot()

        xml_raw = b''.join(
            [s for s in ET.tostring(root).splitlines(True) if s.strip()])  # remove empty lines from string

        dom = minidom.parseString(xml_raw)
        with open(xml_file_path, 'wb') as f:
            f.write(dom.toprettyxml(encoding='utf-8', newl='', indent=''))

    def add_movie_to_xml(self, xml_file_path, id_imdb, id_filelist, **kwargs):
        if id_imdb is None:
            logger.debug('id_imdb is None')

            id_imdb = 'tt0'

        try:
            tree = ET.parse(xml_file_path)
        except Exception as e:
            logger.debug('fisier XML corupt: ' + str(e))

        root = tree.getroot()

        movie = SubElement(root, 'movie', id_imdb=id_imdb)

        for arg_label, arg_value in zip(kwargs, kwargs.values()):
            if arg_label == 'movie_data':
                for param_label, param_value in arg_value.items():
                    if type(param_value) == str:
                        param_value = param_value.replace('"', '\'')

                    exec('{0} = SubElement(movie, "{0}")'.format(param_label))
                    exec('{0}.text = "{1}"'.format(param_label, param_value))

            if arg_label == 'trnt_data':
                trnt = ET.SubElement(movie, 'trnt', id=id_filelist)
                for param_label, param_value in arg_value.items():
                    if type(param_value) == str:
                        param_value = param_value.replace('"', '\'')

                    exec('{0} = SubElement(trnt, "{0}")'.format(param_label))
                    exec('{0}.text = "{1}"'.format(param_label, param_value))

        dom = minidom.parseString(ET.tostring(root))
        with open(xml_file_path, 'wb') as f:
            f.write(dom.toprettyxml(encoding='utf-8'))

    def update_trnt_child_xml(self, xml_file_path, id_imdb, child_name, child_value):
        if id_imdb is None:
            logger.debug('id_imdb is None')

            id_imdb = 'tt0'

        try:
            tree = ET.parse(xml_file_path)
        except Exception as e:
            logger.debug('fisier XML corupt: ' + str(e))

        root = tree.getroot()

        for target in root.findall(".//movie[@id_imdb='" + id_imdb + "']"):
            try:
                target.find(child_name).text = child_value
            except:
                # logger.debug 'lipsa child', child_name
                pass

        dom = minidom.parseString(ET.tostring(root))
        with open(xml_file_path, 'wb') as f:
            f.write(dom.toprettyxml(encoding='utf-8'))

    def find_trnt_elem_xml(self, xml_file_path, elem, attrib, value):
        try:
            tree = ET.parse(xml_file_path)
        except Exception as e:
            logger.debug('fisier XML corupt: ' + str(e))

        root = tree.getroot()

        try:
            if len(root.findall(".//" + elem + "[@" + attrib + "='" + value + "']")) > 0:
                self.find = True
            else:
                self.find = False
        except Exception as e:
            logger.debug('' + str(e))

            self.find = False

    def new_trnt_link_xml(self, xml_file_path, id_imdb, id_filelist, **kwargs):
        try:
            tree = ET.parse(xml_file_path)
        except Exception as e:
            logger.debug('fisier XML corupt: ' + str(e))

        root = tree.getroot()

        movie = root.find(".//movie[@id_imdb='" + id_imdb + "']")

        for arg_label, arg_value in zip(kwargs, kwargs.values()):
            if arg_label == 'trnt_data':
                trnt = ET.SubElement(movie, 'trnt', id=id_filelist)
                for param_label, param_value in arg_value.items():
                    if type(param_value) == str:
                        param_value = param_value.replace('"', '\'')

                    exec('{0} = SubElement(trnt, "{0}")'.format(param_label))
                    exec('{0}.text = "{1}"'.format(param_label, param_value))

        dom = minidom.parseString(ET.tostring(root))
        with open(xml_file_path, 'wb') as f:
            f.write(dom.toprettyxml(encoding='utf-8'))

    def count_xml(self, xml_file_path):
        try:
            tree = ET.parse(xml_file_path)
        except Exception as e:
            logger.debug('fisier XML corupt: ' + str(e))

        root = tree.getroot()

        logger.debug('\ntorrenti noi:', len(root.findall(".//trnt")))

        logger.debug('total filme:', len(list(root)))

        logger.debug('din care')

        new = 0
        tr = 0
        seen = 0
        list_seen = []
        for movie in root:
            if movie.find("seen_type").text == '0':
                new += 1
            elif movie.find("seen_type").text == '1':
                tr += 1
            else:
                seen += 1
                list_seen.append(movie.attrib['id_imdb'])

        logger.debug('- filme noi:', new)

        logger.debug('- torrenti noi:', tr)

        logger.debug('- vazute sau descarcate:', seen)

        self.new_movies = len(list(root))

    def empty_xml(self, xml_file_path):
        try:
            tree = ET.parse(xml_file_path)
        except Exception as e:
            logger.error('fisier XML corupt: ' + str(e))

        root = tree.getroot()

        movie_count = len(root)
        for x in range(movie_count):
            movie = list(root)[0]
            root.remove(movie)

        dom = minidom.parseString(ET.tostring(root))
        with open(xml_file_path, 'wb') as f:
            f.write(dom.toprettyxml(encoding='utf-8'))

    def generate_movie_table(self, movie_template_path, trnt_template_path, mprm, tprm):
        template_file = open(movie_template_path, 'r')
        template = template_file.read()
        template_file.close()

        for key, value in mprm.items():
            if key in template:
                template = self.template_replace(template, key, value)

        template = template.replace('trnt_tbody', self.generate_trnt_table(trnt_template_path, tprm))

        return template + '\n'

    def template_replace(self, template, key, value):
        score_list = ('imdb_score', 'score', 'rott_score', 'meta_score', 'my_imdb_score')
        genre_bad_list = ('Horror', 'Animation')
        country_bad_list = ('India', 'Bahasa indonesia', 'China')

        if value != 'None' and value != 'False' and value != 'N/A' and value is not None:

            if key in score_list:
                class_value = self.get_key_class(key, value)
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

    def generate_trnt_table(self, trnt_template_path, tprm):
        template_file = open(trnt_template_path, 'r')
        template = template_file.read()
        template_file.close()

        trnt_tbody = template
        index = 0

        for key, value in tprm.items():
            if isinstance(value, dict):
                for key2, value2 in value.items():
                    trnt_tbody = trnt_tbody.replace('trnt_id_filelist', key)
                    if value2 == 'True':
                        trnt_tbody = trnt_tbody.replace('trnt_{0}'.format(key2),
                                                        '<img src="https://filelist.io/styles/images/tags/freeleech.png" alt="freeleech" />')
                    elif value2 != 'None' and value2 != 'False' and value2 != 'N/A' and value2 is not None:
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
                    if value == 'True':
                        # trnt_tbody = trnt_tbody.replace('trnt_{0}'.format(key), 'freeleech')
                        trnt_tbody = trnt_tbody.replace('trnt_{0}'.format(key2),
                                                        '<img src="https://filelist.io/styles/images/tags/freeleech.png" alt="freeleech" />')
                    elif value != 'None' and value != 'False' and value != 'N/A' and value is not None:
                        trnt_tbody = template.replace('trnt_{0}'.format(key), value)

        return trnt_tbody

    def generate_email_html(self, template_path, list_new, list_trnt, list_seen, durata):
        # template_file = open('/home/matei/Documents/Python/MoviePediaV2/views/email_filelist.html', 'r')
        template_file = open(template_path, 'r')
        template = template_file.read()
        template_file.close()

        email_body = template

        if not list_new and not list_trnt and not list_seen:
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

            if list_seen != '':
                email_body = email_body.replace('list_seen', list_seen)
            else:
                email_body = email_body.replace('list_seen', '')

            email_body = email_body.replace('prm_durata', '{0}'.format(durata))

        return email_body

    def update_filelist_xml(self, xml_file_path):
        try:
            tree = ET.parse(xml_file_path)
        except Exception as e:
            logger.debug('fisier XML corupt: ' + str(e))

        root = tree.getroot()
        for movie in root:

            if movie.find("title").text is None:
                id_imdb = movie.attrib['id_imdb']
                tmdb = TMDB(id_imdb, '', '')
                tmdb.get_data()

                attrs = vars(tmdb)
                for item in attrs.items():
                    self.update_trnt_child_xml(xml_file_path, tmdb.id_imdb, '{0}'.format(item[0]),
                                               '{0}'.format(item[1]))

                omdb = OMDB(id_imdb)
                omdb.get_data()

                self.update_trnt_child_xml(xml_file_path, omdb.id_imdb, 'rated', '{0}'.format(omdb.rated))
                self.update_trnt_child_xml(xml_file_path, omdb.id_imdb, 'imdb_score', '{0}'.format(omdb.imdb_score))
                self.update_trnt_child_xml(xml_file_path, omdb.id_imdb, 'rott_score', '{0}'.format(omdb.rott_score))
                self.update_trnt_child_xml(xml_file_path, omdb.id_imdb, 'meta_score', '{0}'.format(omdb.meta_score))

        self.xml_pritify(xml_file_path)

    def read_filelist_xml(self, xml_file_path, movie_template_path, trnt_template_path):
        try:
            tree = ET.parse(xml_file_path)
        except Exception as e:
            logger.debug('fisier XML corupt: ' + str(e))

        root = tree.getroot()

        crt_new = 0
        crt_tr = 0
        crt_seen = 0

        list_new = ''
        list_trnt = ''
        list_seen = ''

        for movie in root:

            if movie.find("seen_type").text == '0':
                crt_new += 1
                all_movie = {'crt': '{0}'.format(crt_new), 'id_imdb': '{0}'.format(movie.attrib['id_imdb']),
                             'bck_color': 'F4CCCC'}
                all_trnt = {}
                for trnt in movie.iter('trnt'):
                    # logger.debug trnt.attrib['id']
                    for subelem in list(movie):
                        all_movie[subelem.tag] = subelem.text

                    one_trnt = {}
                    for subelem in list(trnt):
                        one_trnt[subelem.tag] = subelem.text
                    all_trnt[trnt.attrib['id']] = one_trnt

                list_new += self.generate_movie_table(movie_template_path, trnt_template_path, all_movie, all_trnt)

            elif movie.find("seen_type").text == '1':  # FFF2CC
                crt_tr += 1
                all_movie = {'crt': '{0}'.format(crt_tr), 'id_imdb': '{0}'.format(movie.attrib['id_imdb']),
                             'bck_color': 'FFF2CC'}
                all_trnt = {}
                for trnt in movie.iter('trnt'):
                    # logger.debug trnt.attrib['id']
                    for subelem in list(movie):
                        all_movie[subelem.tag] = subelem.text

                    one_trnt = {}
                    for subelem in list(trnt):
                        one_trnt[subelem.tag] = subelem.text
                    all_trnt[trnt.attrib['id']] = one_trnt

                list_trnt += self.generate_movie_table(movie_template_path, trnt_template_path, all_movie, all_trnt)

            else:
                crt_seen += 1  # CFE2F3
                all_movie = {'crt': '{0}'.format(crt_seen), 'id_imdb': '{0}'.format(movie.attrib['id_imdb']),
                             'bck_color': 'CFE2F3'}
                all_trnt = {}
                for trnt in movie.iter('trnt'):
                    # logger.debug trnt.attrib['id']
                    for subelem in list(movie):
                        all_movie[subelem.tag] = subelem.text

                    one_trnt = {}
                    for subelem in list(trnt):
                        one_trnt[subelem.tag] = subelem.text
                    all_trnt[trnt.attrib['id']] = one_trnt

                list_seen += self.generate_movie_table(movie_template_path, trnt_template_path, all_movie, all_trnt)

        # with open('/home/matei/Documents/Python/MoviePediaV2/views/tmp.html', 'w+') as f:
        # 	f.write(list_new + list_trnt + list_seen)
        # f.close

        if list_new:
            list_new = '<h3>FILME NOI:</h3>\n' + list_new
        if list_trnt:
            list_trnt = '<h3>TORRENTI NOI:</h3>\n' + list_trnt
        if list_seen:
            list_seen = '<h3>FILME VAZUTE / TORRENTI DESCARCATI:</h3>\n' + list_seen

        return list_new, list_trnt, list_seen

    def get_key_class(self, key, value):
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


def send_email(items, cypher):
    if items:
        logger.info("Starting emailing routine")
        users = [x for x in get_my_imdb_users() if x['email_newsletters'] == 1]
        for user in users:
            # Filter for each user, with what they've seen
            user_items = check_in_my_movies(items, user['email'])
            if user_items:
                mtls = Mtls()
                mtls.empty_xml(XML_TRNT_PATH)

                for item in user_items:
                    mtls = prepare_item_for_email(item, user['telegram_chat_id'], mtls, cypher)

                mtls.update_filelist_xml(XML_TRNT_PATH)
                mtls.count_xml(XML_TRNT_PATH)

                list_new, list_trnt, list_seen = mtls.read_filelist_xml(XML_TRNT_PATH, MOVIE_TEMPLATE_PATH,
                                                                        TRNT_TEMPLATE_PATH)
                email_body = mtls.generate_email_html(TEMPLATE_PATH, list_new, list_trnt, list_seen, datetime.datetime.now())

                if mtls.new_movies == 1:
                    mail_subject = 'Film nou pe FileList'
                elif mtls.new_movies > 1:
                    mail_subject = '{0} filme noi pe FileList'.format(mtls.new_movies)
                else:
                    mail_subject = 'Nou pe FileList'

                if email_body:
                    logger.info('Sending email')
                    mtls.send_email(PLEX_SERVER_NAME, EMAIL_USER, [user['email']], mail_subject, email_body, '',
                                    EMAIL_HOSTNAME, EMAIL_USER, EMAIL_PASS)
        return
    logger.info('Nothing left to send')


def prepare_item_for_email(item, user_telegram_id, mtls, cypher):
    # Add seen type keys
    if item['already_in_db']:
        item['seen_type'] = 1  # new movie
    else:
        item['seen_type'] = 0  # we have this movie but here's a new torrent for it

    # Convert some keys
    item['size'] = "%.1f" % (item['size'] / 1000000000)
    item['year'] = item['startYear']
    item['genre'] = item['genres']
    item['runtime'] = item['runtimeMinutes']
    item['imdb_score'] = item['averageRating']  # TODO asta nu iese momentan
    item['score'] = item['tmdb_score']
    item['my_imdb_score'] = item['my_score'] if 'my_score' in item.keys() else None
    item['seen_date'] = item['seen_date'] if 'seen_date' in item.keys() else None
    item['resolution'] = str(get_torr_quality(item['name'])) + 'p'
    item['trend'] = ''  # TODO asta nu stiu de unde sa-l iau
    item['id'] = str(item['id'])
    item['freeleech'] = True if item['freeleech'] == 1 else False
    item['trailer'] = item['trailer_link']

    # Add keys for torrent API and generate AES hash for each torrent
    item['torr_link_seed'], item['torr_link_download'] = generate_torr_links(item, user_telegram_id, cypher)

    # Build HTML and return
    mtls.find_trnt_elem_xml(XML_TRNT_PATH, 'movie', 'id_imdb', item['imdb'])
    if mtls.find is False:
        mtls.add_movie_to_xml(XML_TRNT_PATH, item['imdb'], item['id'], movie_data=item,
                              trnt_data=item)
    elif mtls.find is True:
        mtls.find_trnt_elem_xml(XML_TRNT_PATH, 'trnt', 'id', item['id'])
        if mtls.find is False:
            mtls.new_trnt_link_xml(XML_TRNT_PATH, item['imdb'], item['id'],
                                   trnt_data=item)
    mtls.xml_pritify(XML_TRNT_PATH)
    return mtls


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
        lst = []
        for new_m in new:
            d = {
                'already_in_db': False,
                'better_quality': False,
            }
            if new_m['imdb_id'] in [x['imdb_id'] for x in old]:
                old_quality = [x['resolution'] for x in old if x['imdb_id'] == new_m['imdb_id']][0]
                new_quality = int(PTN.parse(new_m['name'])['resolution'][:-1])
                d['already_in_db'] = True
                if int(new_quality) > int(old_quality):
                    d['better_quality'] = True
            lst.append({**new_m, **d})
        return lst

    already_in_db = check_against_user_movies(new_movies, email)
    new = get_intersections(new_movies, already_in_db)
    # Filter out new movies already in database and where quality is the same or poorer
    new = [x for x in new if x['already_in_db'] is False or x['better_quality'] is True]

    return new


def generate_torr_links(item, user_telegram_id, cypher):
    def compose_link(pkg):
        pkg = cypher.encrypt(json.dumps(pkg))
        return f"http://{TORR_API_HOST}:{TORR_API_PORT}{TORR_API_PATH}?{pkg}"
    seed = {
        'id': item['id'],
        'imdb_id': item['imdb_id'],
        'resolution': get_torr_quality(item['name']),
        'folder': TORR_SEED_FOLDER,
        'requested_by': user_telegram_id,
    }
    download = {
        'id': item['id'],
        'imdb_id': item['imdb_id'],
        'resolution': get_torr_quality(item['name']),
        'folder': TORR_DOWNLOAD_FOLDER,
        'requested_by': user_telegram_id,
    }
    return compose_link(seed), compose_link(download)


if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()
    from utils import torr_cypher
    from pprint import pprint
    # test package
    xx = {'id': '751044', 'name': 'Konferentsiya.2020.1080p.HBO.WEB-DL.AAC2.0.H.264-playWEB', 'imdb': 'tt11258824', 'freeleech': True, 'doubleup': 0, 'upload_date': '2021-09-11 00:46:52', 'download_link': 'https://filelist.io/download.php?id=751044&passkey=f5684696415b6f98834f1872bd03a8c1', 'size': '7.1', 'internal': 1, 'moderated': 0, 'category': 'Filme HD-RO', 'seeders': 35, 'leechers': 5, 'times_completed': 54, 'comments': 0, 'files': 1, 'small_description': 'Drama', 'torr_already_processed': False, 'cast': 'Filipp Avdeev, Natalya Tsvetkova, Natalya Pavlenkova, Kseniya Zueva', 'genres': 'drama', 'imdbID': '11258824', 'titleType': 'movie', 'averageRating': 6.8, 'title': 'Conference', 'originalTitle': 'Konferentsiya', 'startYear': '2020', 'numVotes': 306, 'runtimeMinutes': 135, 'imdb_id': '11258824', 'country': None, 'lang': None, 'ovrw': 'Nearly 18 years after the events at the Dubrovka Theatre Centre, Natalia comes to Moscow from her quiet monastic life. Having received a blessing, she brings together the former hostages of the musical show “Nord-Ost” to hold a memorial evening of the tragedy, whose victims they became on 23-26 October 2002. Recreating the details and chronology of events, Natalia plunges into terrible details of her personal story, her fatal mistake, which crossed out her life. Together with other participants of the event and overcoming a post-traumatic syndrome, she must go again through this emotional experience.', 'tmdb_score': 7.0, 'trailer_link': 'https://www.youtube.com/watch?v=qFc3rhleW3I', 'poster': 'https://image.tmdb.org/t/p/w300_and_h450_bestv2/h3JzGzfqN46dZ9yZIElsZ8gOZGa.jpg', 'last_update_tmdb': datetime.datetime(2021, 9, 11, 6, 47, 37, 138038), 'hit_tmdb': True, 'awards': None, 'meta_score': None, 'rated': None, 'rott_score': None, 'omdb_score': None, 'last_update_omdb': datetime.datetime(2021, 9, 11, 7, 38, 16, 361937), 'hit_omdb': False, 'already_in_db': False, 'better_quality': False, 'seen_type': 0, 'year': '2020', 'genre': 'drama', 'runtime': 135, 'imdb_score': 6.8, 'score': 7.0, 'my_imdb_score': None, 'seen_date': None, 'resolution': '1080p', 'trend': '', 'trailer': 'https://www.youtube.com/watch?v=qFc3rhleW3I'}
    seed, dw = generate_torr_links(xx, 1700079840, torr_cypher)
    print(dw)
    x = torr_cypher
    item = "BzNFKOwGt+OGziasVPGStnaAHvwf/2GaIbKSJHQ7fbelg7E4/tnRSY7H9e7+WXtWKKXnqvTetrqJBRiW++QqRgp+bdmszQfo+z4Lq9sdNjrFf+uLwuPOCjVmjncO5VRawzCmmMALWzCBFU+1"
    print(x.decrypt(item))

