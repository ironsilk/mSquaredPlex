# -*- coding: utf-8 -*-


'''
* OMDB Python Lib.
	https://pypi.org/project/omdb/

* OMDB API
	http://www.omdbapi.com/
	http://www.omdbapi.com/?i=tt0368447&apikey=:::your_key:::

* RottenTomatoes Python Lib.
	https://github.com/zachwill/rottentomatoes
'''


import sys
import logging
import datetime
import omdb as omdb_api
from movie import Movie

sys.path.append('/home/matei/Documents/Python/MoviePediaV2/config/')
from mycredentials import sys_omdb


log_file_path = '/home/matei/Documents/Python/MoviePediaV2/logs/{0}-{1}_{2}.log'.format(datetime.date.today().year, datetime.date.today().month, 'my_omdb')
logger = logging.getLogger(__name__)
#logger.setLevel(logging.DEBUG)		#set to DEBUG level
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s %(levelname)s:%(message)s')
file_handler = logging.FileHandler(log_file_path)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.info('===============================================================================================================================')


class OMDB(Movie):

	def __init__(self, id_imdb):
		Movie.__init__ (self, id_imdb)
		self.apikey_omdb	= sys_omdb.passkey


	def get_data(self):
		logger.info('get_data {}'.format(self.id_imdb))
		
		self.genre			= None
		self.lang			= None
		self.imdb_score		= None
		self.rott_score		= None
		self.meta_score		= None
		self.rated			= None
		self.awards			= None
		self.director 		= None
		self.actors 		= None

		try:
			omdb_api.set_default('apikey', self.apikey_omdb)
			raw_omdb = omdb_api.imdbid(self.id_imdb)
		except Exception:
			logger.exception('could not load JSON from omdb for id:{}'.format(self.id_imdb))
			return

		if 'title' in raw_omdb:
			self.title = raw_omdb['title']
		else:
			logger.warning('no "title" in omdb json')

		if 'year' in raw_omdb:
			self.year = raw_omdb['year']
		else:
			logger.warning('no "year" in omdb json')

		if 'country' in raw_omdb:
			self.country = raw_omdb['country']
		else:
			logger.warning('no "country" in omdb json')

		if 'genre' in raw_omdb:
			self.genre = raw_omdb['genre']
		else:
			logger.warning('no "genre" in omdb json')

		if 'language' in raw_omdb:
			self.lang = raw_omdb['language']
		else:
			logger.warning('no "language" in omdb json')

		if 'ratings' in raw_omdb:
			for data in raw_omdb['ratings']:
				if data['source'] == 'Internet Movie Database':
					self.imdb_score = data['value'][:-3]
				elif data['source'] == 'Rotten Tomatoes':
					self.rott_score = data['value'][:-1]
				elif data['source'] == 'Metacritic':
					self.meta_score = data['value'][:-4]
		else:
			logger.warning('no "ratings" in omdb json')

		if 'rated' in raw_omdb:
			self.rated = raw_omdb['rated']
		else:
			logger.warning('no "rated" in omdb json')

		if 'awards' in raw_omdb:
			self.awards = raw_omdb['awards']
		else:
			logger.warning('no "awards" in omdb json')

		if 'director' in raw_omdb:
			self.director = raw_omdb['director']
		else:
			logger.warning('no "director" in omdb json')

		if 'actors' in raw_omdb:
			self.actors = raw_omdb['actors']
		else:
			logger.warning('no "actors" in omdb json')