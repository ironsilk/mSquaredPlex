# -*- coding: utf-8 -*-


'''
* TMDB Python Lib.
	https://github.com/celiao/tmdbsimple/tree/master/tmdbsimple

* TMDB API
	https://www.themoviedb.org/documentation/api
	https://developers.themoviedb.org/3/movies/get-movie-reviews
	https://developers.themoviedb.org/3/getting-started/introduction

* Lang codes
	https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes
'''


import re
import sys
import logging
import datetime
from movie import Movie
import tmdbsimple as tmdb_api

sys.path.append('/home/matei/Documents/Python/MoviePediaV2/config/')
from mycredentials import sys_tmdb


log_file_path = '/home/matei/Documents/Python/MoviePediaV2/logs/{0}-{1}_{2}.log'.format(datetime.date.today().year, datetime.date.today().month, 'my_tmdb')
logger = logging.getLogger(__name__)
#logger.setLevel(logging.DEBUG)		#set to DEBUG level
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s %(levelname)s:%(message)s')
file_handler = logging.FileHandler(log_file_path)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.info('===============================================================================================================================')


class TMDB(Movie):

	def __init__(self, id_imdb, type_tmdb, id_tmdb, search_title=None, search_year=None):
		Movie.__init__ (self, id_imdb)
		self.type_tmdb		= type_tmdb
		self.id_tmdb		= id_tmdb
		self.apikey_tmdb	= sys_tmdb.passkey
		self.search_title 	= search_title
		self.search_year 	= search_year
		self.search_result	= None


	def get_data(self):
		logger.info('get_data {0} / {1} {2}'.format(self.id_imdb, self.type_tmdb, self.id_tmdb))

		self.url 		= None
		self.genre		= None
		self.lang		= None
		self.runtime	= None
		self.ovrw		= None
		self.poster		= None
		self.trailer 	= None
		self.cast 		= None
		self.director	= None
		self.backdrops 	= None

		tmdb_api.API_KEY = self.apikey_tmdb

		if self.id_imdb == '':
			if self.id_tmdb != '':
				if 'movie' in self.type_tmdb:
					self.tmdb_movie()
				elif 'tv' in self.type_tmdb:
					self.tmdb_tv()
				else:
					print 'err tmdb - could not detemine tmdb id (movie or tv) for: {0}'.format(self.id_tmdb)
			elif self.search_title is not None:
				self.tmdb_search()
				logger.debug('to search')
		else:
			try:
				logger.debug('is imdb')
				find = tmdb_api.Find(self.id_imdb)
				response = find.info(external_source='imdb_id')
				if find.movie_results:
					self.id_tmdb = find.movie_results[0]['id']
					self.tmdb_movie()
				else:
					logger.warning('0 results for movie - id imdb:{}'.format(self.id_imdb))
					if find.tv_results:
						self.id_tmdb = find.tv_results[0]['id']
						self.tmdb_tv()
					else:
						logger.warning('0 results for tv shows - id imdb:{}'.format(self.id_imdb))
						return
			except Exception:
				logger.exception('err tmdb - id=tt. Response is: {}'.format(response))
				return

		if self.country is not None:
			cntry_dict = {'United States of America':'USA', 'United Kingdom':'UK', 'GB':'UK', 'FR':'France', 'US':'USA', 'DE':'Germany', 'RU':'Russia'}
			for country_long, country_short in cntry_dict.iteritems():
				self.country = re.sub(r'\b%s\b' % country_long, country_short, self.country)
		
		if self.lang is not None:
			lang_dict = {'en':'English', 'es':'Espanol', 'fr':'Francais', 'de':'Deutsch', 'pl':'Polski', 'shqip':'Albanian', 'bi':'Bislama', 'ky':'Kirghiz', 'tl':'Tagalog', 'ny':'Chichewa', 'st':'Southern Sotho', 'xh':'Xhosa', 'hi':'Hindi', 'tn':'Tswana'}
			for lang_short, lang_long in lang_dict.iteritems():
				self.lang = re.sub(r'\b%s\b' % lang_short.lower(), lang_long, self.lang)
			self.lang = self.lang.title()

	
	def tmdb_movie(self):
		logger.info('tmdb_movie {0}'.format(self.id_tmdb))

		self.type_tmdb = 'movie'

		try:
			movie = tmdb_api.Movies(self.id_tmdb)
			response = movie.info()
			#print response
		except Exception:
			logger.exception('could not load JSON from tmdb for movie id:{}'.format(self.id_tmdb))
			return

		try:
			self.id_imdb = movie.imdb_id
		except Exception:
			logger.exception('')

		try:
			self.url = 'https://www.themoviedb.org/movie/{0}'.format(movie.id)
		except Exception:
			logger.exception('')

		try:
			self.title = movie.title
		except Exception:
			logger.exception('')

		try:
			self.year = movie.release_date[:4]
		except Exception:
			logger.exception('')

		# obtine doar primele 4 genre
		try:
			if movie.genres:
				genre = movie.genres[0]['name']
				for x in range(3):
					try:
						genre = '{0}, {1}'.format(genre, movie.genres[x+1]['name'])
					except:
						break
				self.genre = genre
			else:
				logger.warning('no "genre" value available')
		except Exception:
			logger.exception('')

		# obtine doar primele 4 country
		try:
			if movie.production_countries:
				country = movie.production_countries[0]['name']
				for x in range(3):
					try:
						country = '{0}, {1}'.format(country, movie.production_countries[x+1]['name'])
					except:
						break
				self.country = country
			else:
				logger.warning('no "production_countries" value available')
		except Exception:
			logger.exception('')

		# obtine doar primele 4 lang
		try:
			if movie.spoken_languages:
				lang = movie.spoken_languages[0]['name']
				if lang == '' or lang == '??????':
					lang = movie.spoken_languages[0]['iso_639_1']
					logger.warning('weird lang - iso_639_1 code is:{}'.format(lang))
				for x in range(3):
					try:
						if movie.spoken_languages[x+1]['name'] != '':
							lang = '{0}, {1}'.format(lang, movie.spoken_languages[x+1]['name'])
						else:
							lang = '{0}, {1}'.format(lang, movie.spoken_languages[x+1]['iso_639_1'])
							logger.warning('weird lang - iso_639_1 code is:{}'.format(lang))
					except:
						break
				self.lang = lang
			else:
				logger.warning('no "languages" value available')
		except Exception:
			logger.exception('')

		try:
			self.score = movie.vote_average
		except Exception:
			logger.exception('')

		try:
			self.runtime = movie.runtime
		except Exception:
			logger.exception('')

		try:
			self.ovrw = movie.overview.replace('\n', '').replace('\r', '')
		except Exception:
			logger.exception('')

		try:
			self.poster = 'https://image.tmdb.org/t/p/w300_and_h450_bestv2{0}'.format(movie.poster_path)
		except Exception:
			logger.exception('')

		try:
			response = movie.videos()
		except Exception:
			logger.exception('')

		try:
			for x in movie.results:
				if x['type'] == 'Trailer' and x['site'] == 'YouTube':
					if x['key'] is not None:
						self.trailer = 'https://www.youtube.com/watch?v={0}'.format(x['key'])
					break
		except Exception:
			logger.exception('')

		try:
			response = movie.credits()
		except Exception:
			logger.exception('')

		try:
			temp_cast = ''
			for s in movie.cast[:5]:
				temp_cast = '{0}, {1}'.format(temp_cast, s['name'].encode('utf-8'))
			self.cast = temp_cast[2:]
		except Exception:
			logger.exception('')

		try:
			for s in movie.crew:
				if s['job'] == 'Director':
					self.director = s['name']
		except Exception:
			logger.exception('')

		try:
			response = movie.images()
		except Exception:
			logger.exception('')

		try:
			backdrops = []
			for s in movie.backdrops:
				backdrops.append('http://image.tmdb.org/t/p/w1280{0}'.format(s['file_path']))
			self.backdrops = backdrops
		except Exception:
			logger.exception('')


	def tmdb_tv(self):
		logger.info('tmdb_tv {0}'.format(self.id_tmdb))

		self.type_tmdb = 'tv'

		try:
			tv = tmdb_api.TV(self.id_tmdb)
			response = tv.info()
		except Exception:
			logger.exception('')

		try:
			self.url = 'https://www.themoviedb.org/tv/{0}'.format(self.id_tmdb)
		except Exception:
			logger.exception('')

		try:
			self.title = tv.name
		except Exception:
			logger.exception('')

		try:
			self.year = tv.first_air_date[:4]
		except Exception:
			logger.exception('')

		try:
			if tv.genres:
				genre = tv.genres[0]['name']
				for x in range(3):
					try:
						genre = '{0}, {1}'.format(genre, tv.genres[x+1]['name'])
					except:
						break
				self.genre = genre
			else:
				logger.warning('no "genre" value available')
		except Exception:
			logger.exception('')

		# obtine doar primele 4 country
		try:
			if tv.origin_country:
				if 'name' in tv.origin_country[0]:
					country = tv.origin_country[0]['name']
				else:
					country = tv.origin_country[0]
				for x in range(3):
					try:
						if 'name' in tv.origin_country[0]:
							country = '{0}, {1}'.format(country, tv.origin_country[x+1]['name'])
						else:
							country = '{0}, {1}'.format(country, tv.origin_country[x+1])
					except:
						break
				self.country = country
			else:
				logger.warning('no "origin_country" value available')
		except Exception:
			logger.exception('')

		# obtine doar primele 4 lang
		try:
			if tv.languages:
				if 'name' in tv.languages:
					lang = tv.languages[0]['name']
				else:
					lang = tv.languages[0]
				for x in range(3):
					try:
						if 'name' in tv.languages[0]:
							lang = '{0}, {1}'.format(lang, tv.languages[x+1]['name'])
						else:
							lang = '{0}, {1}'.format(lang, tv.languages[x+1])
					except:
						break
				self.lang = lang
			else:
				logger.warning('no "languages" value available')
		except Exception:
			logger.exception('')

		try:
			self.score = tv.vote_average
		except Exception:
			logger.exception('')

		try:
			self.ovrw = tv.overview.replace('\n', '').replace('\r', '')
		except Exception:
			logger.exception('')

		try:
			self.poster = 'https://image.tmdb.org/t/p/w300_and_h450_bestv2{0}'.format(tv.poster_path)
		except Exception:
			logger.exception('')

		try:
			response = tv.videos()
		except Exception:
			logger.exception('')

		try:
			for x in tv.results:
				if x['type'] == 'Trailer' and x['site'] == 'YouTube':
					if x['key'] is not None:
						self.trailer = 'https://www.youtube.com/watch?v={0}'.format(x['key'])
					break
		except Exception:
			logger.exception('')

		try:
			response = tv.credits()
		except Exception:
			logger.exception('')

		try:
			temp_cast = ''
			for s in tv.cast[:5]:
				temp_cast = '{0}, {1}'.format(temp_cast, s['name'].encode('utf-8'))
			self.cast = temp_cast[2:]
		except Exception:
			logger.exception('')

		try:
			for s in tv.crew:
				if s['job'] == 'Director':
					self.director = s['name']
		except Exception:
			logger.exception('')
		
		try:
			response = tv.images()
		except Exception:
			logger.exception('')

		try:
			backdrops = []
			for s in tv.backdrops:
				backdrops.append('http://image.tmdb.org/t/p/w1280{0}'.format(s['file_path']))
			self.backdrops = backdrops
		except Exception:
			logger.exception('')


	def tmdb_search(self):
		logger.info('tmdb_search movie title & year: {0} {1}'.format(self.search_title, self.search_year))
		try:
			search = tmdb_api.Search()
			response = search.movie(query=self.search_title)
			# print response
		except Exception:
			logger.exception('')

		try:
			for s in search.results:
				if self.search_year != None and self.search_year == int(s['release_date'][:4]):
					self.title 	= s['title']
					self.id_tmdb= s['id']
					self.year 	= int(s['release_date'][:4])
					self.score 	= s['popularity']
					self.search_result = 'based on title and year'
					break
			if self.id_tmdb is None:
				self.title 	= s['title']
				self.id_tmdb= s['id']
				self.year 	= int(s['release_date'][:4])
				self.score 	= s['popularity']
				self.search_result = 'based only on title'
		except Exception:
			logger.exception('')