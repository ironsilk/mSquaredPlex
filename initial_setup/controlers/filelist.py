#!/usr/local/python
#-*- coding: iso8859-2 -*-

# python /home/matei/Documents/Python/MoviePediaV2/controllers/filelist.py

'''                                                                            
Wonder 2017
	http://filelist.ro/details.php?id=549536
	https://www.themoviedb.org/movie/406997-wonder
	http://www.imdb.com/title/tt2543472/
	https://www.rottentomatoes.com/m/wonder/
	http://www.metacritic.com/movie/wonder


import os
import sys
import json
import simplejson
import codecs
import logging
import gspread # google
import traceback
import feedparser # RSS/XML feeds
import datetime
import xml.etree.ElementTree as ET
from oauth2client.service_account import ServiceAccountCredentials

sys.path.append('/home/matei/Documents/Python/MoviePediaV2/models/')
from my_imdb import IMDB
from my_omdb import OMDB
from my_tmdb import TMDB
from my_flst import Filelist
from movie import Movie
from mtls import Mtls

sys.path.append('/home/matei/Documents/Python/MoviePediaV2/config/')
import config as cfg
from mycredentials import sys_filelist, sys_email, sys_rss_filelist, sys_tmdb, sys_omdb

reload(sys)  
sys.setdefaultencoding('utf8')


filelist = Filelist()
movie = Movie('')
mtls = Mtls()


#citeste un feed dat
def read_rss (vurlfeed):
	logger.info('[readFListfeed] Start')
	try:
		d = feedparser.parse(vurlfeed)
	except Exception as vErr:
		logger.error('[readFListfeed] Nu am putut parsa feed-ul File List: '+ str(vErr))

	logger.info('[readFListfeed] Succes')
	return d


def update_my_imdb (profile_id, id_imdb_xls_list):
	logger.info('[update_myIMDBscore] Start!')

	worksheet = sheet.worksheet('myIMDB')

	imdb_user = IMDB('')
	imdb_user.get_user_ratings(profile_id)

	for id_imdb in imdb_user.ratings.keys():
		if id_imdb not in id_imdb_xls_list:
			id_imdb_xls_list.append(id_imdb)
			worksheet.append_row([id_imdb, imdb_user.ratings[id_imdb]['rating'], imdb_user.ratings[id_imdb]['date']])
			logger.info('[update_myIMDBscore] APPEND: {0}'.format(id_imdb))

	logger.info('[update_myIMDBscore] Succes')


def durataPy(oraStart):
	oraEnd = datetime.datetime.now()
	durata = datetime.datetime.strptime(oraEnd.time().strftime('%H:%M:%S'),'%H:%M:%S') - datetime.datetime.strptime(oraStart.time().strftime('%H:%M:%S'),'%H:%M:%S')

	return durata


log_file_path = '/home/matei/Documents/Python/MoviePediaV2/logs/{0}-{1}_{2}.log'.format(datetime.date.today().year, datetime.date.today().month, 'filelist')
logger = logging.getLogger(__name__)
#logger.setLevel(logging.DEBUG)		#set to DEBUG level
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s %(levelname)s:%(message)s')
file_handler = logging.FileHandler(log_file_path)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.info('===============================================================================================================================')


oraStart = datetime.datetime.now()
print oraStart.strftime('%Y-%m-%d %H:%M:%S'), '- Incepe verificarea de torrenti noi \n'


creds = ServiceAccountCredentials.from_json_keyfile_name(cfg.google_cred, 'https://spreadsheets.google.com/feeds')
client = gspread.authorize(creds)


index = 0
trntNoi = 0
filmeNoi = 0
gasit = 0

vHTML10 = ''
vHTML20 = ''
vHTMLX1 = ''

vCnt10 = 0
vCnt20 = 0
vCntX1 = 0


mtls.empty_xml(cfg.xml_trnt_path)


sheet = client.open(cfg.gsheet_name)
wsheet_rss = sheet.worksheet('RSS')
list_rss = wsheet_rss.col_values(2) 		#rss date
wsheet_flist = sheet.worksheet('FLIST')
list_flist = wsheet_flist.col_values(1)		#id_filelist
wsheet_tmdb = sheet.worksheet('TMDB')
list_tmdb = wsheet_tmdb.col_values(1)		#idIMDB
wsheet_omdb = sheet.worksheet('OMDB')			
list_omdb = wsheet_omdb.col_values(1)		#idIMDB
wsheet_my_imdb = sheet.worksheet('myIMDB')			
list_my_imdb01 = wsheet_my_imdb.col_values(1)	#idIMDB
list_my_imdb02 = wsheet_my_imdb.col_values(2)	#my_imdb_score
list_my_imdb03 = wsheet_my_imdb.col_values(3)	#seen_date
wsheetLOG = sheet.worksheet('LOG')

update_my_imdb(cfg.imdb_profile, list_my_imdb01)

movie.get_movie_dblist(cfg.db_path)

filelist_rss_url = '{0}{1}'.format(cfg.filelist_rss_url, sys_rss_filelist.passkey)
rss_data = read_rss(filelist_rss_url)
#rss_data = read_rss('http://www.campulverde.info/rss.xml')

list_rss_new = []
list_id_imdb_new = []
for rss_item in rss_data.entries:
	filelist.get_rss_data(rss_item)

	if filelist.rss_date not in list_rss:
		list_rss_new.append(filelist.id_filelist)
		
		if filelist.rss_id_imdb is not None:
			list_id_imdb_new.append(filelist.rss_id_imdb)
			movie_data = {'seen_type':'', 'title':'', 'year':'', 'genre':'', 'rated':'', 'country':'', 'runtime':'', 'imdb_score':'', 'score':'', 'rott_score':'', 'meta_score':'', 'ovrw':'', 'director':'', 'cast':'', 'poster':'', 'trailer':'', 'my_imdb_score':'', 'seen_date':''}
		else:
			movie_data = {'seen_type':'0', 'title':filelist.rss_title, 'year':filelist.rss_year, 'genre':'', 'rated':'', 'country':'', 'runtime':'', 'imdb_score':'', 'score':'', 'rott_score':'', 'meta_score':'', 'ovrw':'', 'director':'', 'cast':'', 'poster':'https://www.bioskoptoday.com/wp-content/themes/bioskoptodaytheme/images/no-poster.png', 'trailer':'', 'my_imdb_score':'', 'seen_date':''}

		wsheet_rss.append_row([filelist.id_filelist, filelist.rss_date, filelist.rss_id_imdb, filelist.rss_name, filelist.rss_link, filelist.rss_resolution, filelist.rss_quality, filelist.rss_year, filelist.rss_freeleech, filelist.rss_internal, filelist.rss_size, oraStart])

		trnt_data = {'resolution':filelist.rss_resolution, 'size':int(filelist.rss_size), 'freeleech':filelist.rss_freeleech, 'trend':''}

		if filelist.rss_id_imdb not in list_tmdb:
			movie_data['seen_type'] = 0
		else:
			movie_data['seen_type'] = 1
		
		if filelist.rss_id_imdb in list_my_imdb01 or filelist.rss_id_imdb in movie.id_list and filelist.rss_id_imdb is not None:
			movie_data['seen_type'] = 2

		if filelist.rss_id_imdb in list_my_imdb01:
			my_index = list_my_imdb01.index(filelist.rss_id_imdb)
			movie_data['my_imdb_score'] = list_my_imdb02[my_index]
			movie_data['seen_date'] = '{0}:'.format(list_my_imdb03[my_index][:-3])

		mtls.find_trnt_elem_xml(cfg.xml_trnt_path, 'movie', 'id_imdb', filelist.rss_id_imdb)
		if mtls.find is False:
			mtls.add_movie_to_xml(cfg.xml_trnt_path, filelist.rss_id_imdb, filelist.id_filelist, movie_data=movie_data, trnt_data=trnt_data)
		elif mtls.find is True:
			mtls.find_trnt_elem_xml(cfg.xml_trnt_path, 'trnt', 'id', filelist.id_filelist)
			if mtls.find is False:
				mtls.new_trnt_link_xml(cfg.xml_trnt_path, filelist.rss_id_imdb, filelist.id_filelist, trnt_data=trnt_data)
		mtls.xml_pritify(cfg.xml_trnt_path)

print '{0} feed-uri noi'.format(len(list_rss_new))


if list_rss_new:
	for new_id_filelist in list_rss_new:

		if new_id_filelist not in list_flist:
			list_flist.append(new_id_filelist)
			filelist.get_movie_ids(new_id_filelist)

			wsheet_flist.append_row([new_id_filelist, filelist.id_imdb, filelist.id_type, filelist.id_tmdb, oraStart])

	print 'flist-uri noi'


if list_id_imdb_new:
	for new_id_imdb in list_id_imdb_new:

		if new_id_imdb not in list_tmdb:
			list_tmdb.append(new_id_imdb)
			tmdb = TMDB(new_id_imdb, '', '')
			tmdb.get_data()

			wsheet_tmdb.append_row([tmdb.id_imdb, tmdb.type_tmdb, tmdb.id_tmdb, tmdb.title, tmdb.year, tmdb.lang, tmdb.genre, tmdb.score, tmdb.poster, tmdb.ovrw, tmdb.runtime, tmdb.country, tmdb.url, oraStart])

			attrs = vars(tmdb)
			for item in attrs.items():
				mtls.update_trnt_child_xml(cfg.xml_trnt_path, tmdb.id_imdb, '{0}'.format(item[0]), '{0}'.format(item[1]))
			mtls.xml_pritify(cfg.xml_trnt_path)

	print 'TMDB-uri noi'


if list_id_imdb_new:
	for new_id_imdb in list_id_imdb_new:

		if new_id_imdb not in list_omdb:
			list_omdb.append(new_id_imdb)
			omdb = OMDB(new_id_imdb)
			omdb.get_data()

			wsheet_omdb.append_row([omdb.id_imdb, omdb.title, omdb.year, omdb.genre, omdb.rated, omdb.country, omdb.lang, omdb.awards, omdb.imdb_score, omdb.rott_score, omdb.meta_score, oraStart])

			mtls.update_trnt_child_xml(cfg.xml_trnt_path, omdb.id_imdb, 'rated', '{0}'.format(omdb.rated))
			mtls.update_trnt_child_xml(cfg.xml_trnt_path, omdb.id_imdb, 'imdb_score', '{0}'.format(omdb.imdb_score))
			mtls.update_trnt_child_xml(cfg.xml_trnt_path, omdb.id_imdb, 'rott_score', '{0}'.format(omdb.rott_score))
			mtls.update_trnt_child_xml(cfg.xml_trnt_path, omdb.id_imdb, 'meta_score', '{0}'.format(omdb.meta_score))
			mtls.xml_pritify(cfg.xml_trnt_path)

	print 'OMDB-uri noi'

mtls.update_filelist_xml(cfg.xml_trnt_path)

mtls.count_xml(cfg.xml_trnt_path)

list_new, list_trnt, list_seen = mtls.read_filelist_xml(cfg.xml_trnt_path, cfg.movie_template_path, cfg.trnt_template_path)

email_body = mtls.generate_email_html(cfg.template_path, list_new, list_trnt, list_seen, durataPy(oraStart))


if mtls.new_movies == 1:
	mail_subject = 'Film nou pe FileList'
elif mtls.new_movies > 1:
	mail_subject = '{0} filme noi pe FileList'.format(mtls.new_movies)
else:
	mail_subject = 'Nou pe FileList'

print mail_subject

if email_body:
	print 'trimit mail'
	mtls.send_email('TeleCinemateca', sys_email.username, cfg.email_list_debug, mail_subject, email_body, '', sys_email.hostname, sys_email.username, sys_email.password)
else:
	print 'nimic de trimis pe mail'

'''