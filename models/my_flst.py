# -*- coding: utf-8 -*-


import re
import sys
import PTN
import logging
import datetime
import requests
from urlparse import urlparse
from bs4 import BeautifulSoup

sys.path.append('/home/matei/Documents/Python/MoviePediaV2/config/')
from mycredentials import sys_rss_filelist, sys_filelist

reload(sys)  
sys.setdefaultencoding('utf8')


log_file_path = '/home/matei/Documents/Python/MoviePediaV2/logs/{0}-{1}_{2}.log'.format(datetime.date.today().year, datetime.date.today().month, 'my_flst')
logger = logging.getLogger(__name__)
#logger.setLevel(logging.DEBUG)		#set to DEBUG level
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s %(levelname)s:%(message)s')
file_handler = logging.FileHandler(log_file_path)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.info('===============================================================================================================================')


class Filelist:

	def __init__(self):
		self.id_filelist	= None
		self.id_imdb 		= None


	def get_rss_data(self, rss_item):
		logger.debug(rss_item)

		self.rss_item		= rss_item
		self.rss_date		= self.rss_item.published
		self.rss_name		= self.rss_item.title
		self.rss_desc		= self.rss_item.description
		self.rss_link		= self.rss_item.link
		self.rss_title		= None
		self.rss_resolution	= None
		self.rss_quality 	= None
		self.rss_year		= None
		self.rss_size		= 0
		self.rss_id_imdb	= None
		self.rss_freeleech	= False
		self.rss_internal	= False

		vPTN = PTN.parse(self.rss_item.title)

		#obtine rezolutie torrent, daca exista in denumire torrent
		try:
			self.rss_title = vPTN['title']
		except Exception:
			logger.exception('')

		#obtine rezolutie torrent, daca exista in denumire torrent
		try:
			self.rss_resolution = vPTN['resolution']
		except Exception:
			logger.warning('no "resolution" value found in: {}'.format(self.rss_name))

		#obtine calitate torrent, daca exista in denumire torrent
		try:
			self.rss_quality = vPTN['quality']
		except Exception:
			logger.warning('no "quality" value found in: {}'.format(self.rss_name))

		#obtine an film, daca exista in denumire torrent
		try:
			self.rss_year = vPTN['year']
		except Exception:
			logger.warning('no "year" value found in: {}'.format(self.rss_name))

		#obtine FreeLeech torrent, daca exista in denumire torrent
		if '[FreeLeech]' in self.rss_item.title:
			self.rss_freeleech = True

		#obtine Internal torrent, daca exista in denumire torrent
		if '[Internal]' in self.rss_item.title:
			self.rss_internal = True

		#obtine size torrent, daca este precizat in descriere rss
		try:
			trDesc = self.rss_desc.split ('\n',5)
			self.rss_size = float(re.search('%s(.*)%s' % ('Size: ', ' GB'), trDesc[2]).group(1))
		except Exception:
			logger.exception('')

		#obtine link imdb, daca este precizat in descriere rss
		try:
			if 'iMDB: http://www.imdb.com/title/' in trDesc[4]:
				self.rss_id_imdb = trDesc[4].replace('iMDB: http://www.imdb.com/title/', '')
			else:
				logger.warning('could not determine "id imdb" from rss description')
		except Exception:
			logger.exception('')

		try:
			string_1 = 'https://filelist.io/download.php?id='
			string_2 = '&passkey={0}'.format(sys_rss_filelist.passkey)
			self.id_filelist = self.rss_link.replace(string_1, '').replace(string_2, '')
		except Exception:
			logger.exception('')


	def get_html(self, url):
		logger.info('get_html for {0}'.format(url))

		try:
			html = None
			s = requests.session()
			html = s.get('https://filelist.io/login.php')

			soup = BeautifulSoup(html.content, 'html5lib')
			valid = soup.find('input', attrs={'name': 'validator'})['value']

			auth = {'username': sys_filelist.username, 'password': sys_filelist.password, 'returnto': '%2F', 'validator': valid}
			loginRequest = s.post('https://filelist.io/takelogin.php', data=auth)
			#print loginRequest.status_code

			html = s.get(url).text

			if 'Broblem ? ' in html:
				logger.exception('Sign in failed!')
				html = None
		except Exception:
			logger.exception('Could not sign in!')
			html = None

		return html


	def get_movie_ids(self, id_filelist):
		logger.info('get_movie_ids for {}'.format(id_filelist))

		self.id_type		= None
		self.id_tmdb 		= None
		self.id_imdb		= None

		url = 'https://filelist.io/details.php?id={0}'.format(id_filelist)
		html = self.get_html(url)

		if (html != None):
			try:
				urls = re.findall('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', html)
				for url in urls:
					#alege numai url-ul tmdb
					o = urlparse(url)
					if (o.netloc == 'www.themoviedb.org'):
						slashparts = url.split('/')
						self.id_tmdb = slashparts[4][:-1]
						self.id_type = re.search('%s(.*)%s' % ('/', '/'), o.path).group(1)
			except Exception:
				logger.exception('type & id TMDB')

			try:
				soup_flist = BeautifulSoup(html, 'html.parser')
				for a in soup_flist.find_all('a', href=True):
					if (a['href'][:27] == 'https://www.imdb.com/title/'):
						self.id_imdb = a['href'][27:]
						break
			except Exception:
				logger.exception('idIMDB')

		else:
			logger.warning('html = None')

	
	def get_ratio(self):
		logger.info('get_ratio')

		self.ratio 			= None 

		url = 'https://filelist.io/index.php'
		html = self.get_html(url)

		if (html != None):
			try:
				self.soup_flist = BeautifulSoup(html, 'html.parser')
				for a in self.soup_flist.find_all('span', style='margin-right:5px;'):
					if (a.get_text()[:6] == ' Ratio'):
						self.ratio = a.get_text()[7:]
						break
			except Exception:
				logger.exception('Ratio')