import datetime
from email_tools import Mtls
from torr_tools import get_torr_quality
from settings import xml_trnt_path, template_path, movie_template_path, trnt_template_path

x = {'already_in_db': False,
 'averageRating': 5.4,
 'awards': '3 nominations',
 'better_quality': False,
 'category': 'Filme HD-RO',
 'comments': 0,
 'country': 'Italy',
 'doubleup': 0,
 'download_link': 'https://filelist.io/download.php?id=748320&passkey=f5684696415b6f98834f1872bd03a8c1',
 'endYear': None,
 'files': 1,
 'freeleech': 0,
 'genres': 'Comedy,Drama,Romance',
 'hit_omdb': 1,
 'hit_tmdb': 1,
 'id': 748320,
 'imdb': 'tt11154906',
 'imdb_id': 11154906,
 'internal': 0,
 'isAdult': 0,
 'lang': 'Italian',
 'last_update_omdb': datetime.datetime(2021, 8, 18, 15, 19, 56),
 'last_update_tmdb': datetime.datetime(2021, 8, 18, 15, 19, 55),
 'leechers': 0,
 'meta_score': None,
 'moderated': 1,
 'name': 'Out.of.My.League.2020.720p.WEB-DL.DD+5.1.H.264-NAISU',
 'numVotes': 338,
 'originalTitle': 'Sul più bello',
 'ovrw': 'Marta may be an orphan, and she may be affected by a lethal '
         'illness, yet she is the most positive person one can meet. She '
         'wants a boy to fall for her. Not any boy - the most handsome of '
         'them all. One day, she may have found her match.',
 'primaryTitle': 'Out of My League',
 'rated': None,
 'rott_score': None,
 'runtimeMinutes': 91,
 'score': None,
 'seeders': 20,
 'size': 1340928446,
 'small_description': 'Comedy, Drama, Romance',
 'startYear': 2020,
 't_soundex': 'O3154',
 'tconst': 11154906,
 'times_completed': 28,
 'title': 'Sul più bello',
 'titleType': 'movie',
 'torr_already_seen': False,
 'trailer_link': 'https://www.youtube.com/watch?v=PQM54p9IKZs',
 'upload_date': '2021-08-18 11:30:23'}


def prepare_for_email(item):
    if item['hit_tmdb'] == 0:
        item['seen_type'] = 0
    else:
        item['seen_type'] = 1
    if item['already_in_db']:
        item['seen_type'] = 2
    item['year'] = item['startYear']
    item['genre'] = item['genres']
    item['runtime'] = item['runtimeMinutes']
    item['imdb_score'] = item['averageRating']
    item['director'] = 'DIRECTOR'  # TODO
    item['cast'] = 'CAST'  # TODO
    item['poster'] = None  # TODO
    item['my_imdb_score'] = None  # TODO
    item['seen_date'] = None  # TODO

    item['resolution'] = get_torr_quality(item['name'])
    item['trend'] = ''  # TODO
    item['id'] = str(item['id'])

    mtls.find_trnt_elem_xml(xml_trnt_path, 'movie', 'id_imdb', item['imdb'])
    if mtls.find is False:
        mtls.add_movie_to_xml(xml_trnt_path, item['imdb'], item['id'], movie_data=item,
                              trnt_data=item)
    elif mtls.find is True:
        mtls.find_trnt_elem_xml(xml_trnt_path, 'trnt', 'id', item['id'])
        if mtls.find is False:
            mtls.new_trnt_link_xml(xml_trnt_path, item['imdb'], item['id'],
                                   trnt_data=item)
    mtls.xml_pritify(xml_trnt_path)


mtls = Mtls()

mtls.empty_xml(xml_trnt_path)

for item in [x]:
    prepare_for_email(item)

mtls.update_filelist_xml(xml_trnt_path)

mtls.count_xml(xml_trnt_path)

list_new, list_trnt, list_seen = mtls.read_filelist_xml(xml_trnt_path, movie_template_path,
                                                        trnt_template_path)

email_body = mtls.generate_email_html(template_path, list_new, list_trnt, list_seen, datetime.datetime.now())

if mtls.new_movies == 1:
    mail_subject = 'Film nou pe FileList'
elif mtls.new_movies > 1:
    mail_subject = '{0} filme noi pe FileList'.format(mtls.new_movies)
else:
    mail_subject = 'Nou pe FileList'

print(mail_subject)

if email_body:
    print(email_body)
    print('trimit mail')
    # mtls.send_email('TeleCinemateca', sys_email.username, email_list_debug, mail_subject, email_body, '',
    #                 sys_email.hostname, sys_email.username, sys_email.password)
else:
    print('nimic de trimis pe mail')