# -*- coding: utf-8 -*-

import re
import json
import logging
import requests
import datetime
from movie import Movie
from bs4 import BeautifulSoup


log_file_path = '/home/matei/Documents/Python/MoviePediaV2/logs/{0}-{1}_{2}.log'.format(datetime.date.today().year, datetime.date.today().month, 'my_imdb')
logger = logging.getLogger(__name__)
#logger.setLevel(logging.DEBUG)		#set to DEBUG level
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s %(levelname)s:%(message)s')
file_handler = logging.FileHandler(log_file_path)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.info('===============================================================================================================================')


class IMDB(Movie):

	def get_data(self):
		logger.info('get_data for {}'.format(self.id_imdb))

		self.url 		= 'https://www.imdb.com/title/{0}/'.format(self.id_imdb)
		self.rated 		= None
		self.json 		= None
		
		try:
			self.soup_imdb	= BeautifulSoup(requests.get(self.url).text, 'html.parser')
		except:
			logger.exception('could not load html from imdb:{}'.format(self.url))
			return

		# get title & year by parsing
		try:
			title_year = None
			try:
				imdb_title = self.soup_imdb.find('div', class_ = 'title_wrapper').find('h1', class_ = '').get_text()
			except:
				imdb_title = self.soup_imdb.find('div', class_ = 'title_wrapper').find('h1', class_ = 'long').get_text()
			title_year = imdb_title.rstrip()
			logger.debug(title_year)
		except Exception:
			logger.exception('')

		# determine title
		try:
			if title_year[-6] == '(' and title_year[-1] == ')':
				self.title = title_year[:-7]
			else:
				self.title = title_year
		except Exception:
			logger.exception('')

		# get country by parsing
		try:
			country = None
			for a in self.soup_imdb.find_all('a', href=True):
				if a['href'][:21] == '/search/title?country':
					if country is None:
						country = a.get_text()
					else:
						country = '{0}, {1}'.format(country, a.get_text())
			self.country = country
		except Exception:
			logger.exception('')

		# load JSON from header
		try:
			self.JSON = json.loads(self.soup_imdb.find('script', type = 'application/ld+json').get_text())
		except Exception:
			logger.exception('could not load JSON from imdb html:{}'.format(self.url))
			return

		# get year from JSON
		if 'datePublished' in self.JSON:
			self.year = self.JSON['datePublished'][:4]
		else:
			logger.warning('no "datePublished" in imdb json')

		# get score from JSON
		if 'aggregateRating' in self.JSON and 'ratingValue' in self.JSON['aggregateRating']:
			self.score = self.JSON['aggregateRating']['ratingValue']
		else:
			logger.warning('no "ratingValue" in imdb json')

		# get rated from JSON
		if 'contentRating' in self.JSON:
			self.rated = self.JSON['contentRating']
		else:
			logger.warning('no "contentRating" in imdb json')

	def get_user_ratings(self, profile_id):
		logger.info('get_user_ratings for {}'.format(profile_id))

		self.profile_id	= profile_id
		self.ratings = None

		try:
			url = 'https://www.imdb.com/user/ur{0}/ratings'.format(self.profile_id)
			soup_imdb = BeautifulSoup(requests.get(url).text, 'html.parser')
			titles = int(soup_imdb.find('div', class_='lister-list-length').find('span', id='lister-header-current-size').get_text().replace(',',''))
			pages = titles/100
		except Exception:
			pages = 0
			logger.exception('could not determine movies and pages')
		logger.debug('{0} titles found in {1} pages'.format(titles, pages))

		try:
			results	= {}
			#for page in range(pages + 1): 
			for page in range(1):	#se pare ca dictionarul devine prea mare si face crush pythonul asa ca incarcam numai prima pagina
				ids = soup_imdb.findAll ('div', {'class' : 'lister-item-image ribbonize'})
				ratings = soup_imdb.findAll ('div', {'class' : 'ipl-rating-star ipl-rating-star--other-user small'})
				dates = []

				for y in soup_imdb.findAll ('p', {'class' : 'text-muted'}):
					if str(y)[:30] == '<p class="text-muted">Rated on':
						date = re.search('%s(.*)%s' % ('Rated on ', '</p>'), str(y)).group(1)
						dates.append(date)

				try:
					last_page = False
					next_url = soup_imdb.find ('a', {'class' : 'flat-button lister-page-next next-page'})['href']
				except:
					last_page = True

				for x, y, z in zip(ids, ratings, dates):
					imdb_id = x['data-tconst']
					rating 	= int(y.get_text())
					date 	= datetime.datetime.strptime(z, '%d %b %Y')
					date 	= date.strftime('%Y-%m-%d')
					results.update({imdb_id:{'rating' : rating, 'date': date}})

				if last_page != True:
					next_url = 'https://www.imdb.com{0}'.format(next_url)
					soup_imdb = BeautifulSoup(requests.get(next_url).text, 'html.parser')

			self.ratings = results
		
		except Exception:
			logger.exception('')