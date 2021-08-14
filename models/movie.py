# -*- coding: utf-8 -*-


import sys
import logging
import datetime
import xml.etree.ElementTree as ET

reload(sys)  
sys.setdefaultencoding('utf8')


log_file_path = '/home/matei/Documents/Python/MoviePediaV2/logs/{0}-{1}_{2}.log'.format(datetime.date.today().year, datetime.date.today().month, 'movie')
logger = logging.getLogger(__name__)
#logger.setLevel(logging.DEBUG)		#set to DEBUG level
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s %(levelname)s:%(message)s')
file_handler = logging.FileHandler(log_file_path)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.info('===============================================================================================================================')


class Movie:
	
	def __init__(self, id_imdb):	
		self.id_imdb 	= id_imdb
		self.title 		= None
		self.year 		= None
		self.country 	= None
		self.score 		= None


	def get_movie_dblist(self, xml_path):
		self.id_list = []

		try:
			XMLtree	= ET.parse(xml_path)
			XMLroot	= XMLtree.getroot()
			for child in XMLroot:
				self.id_list.append(child.find('imdb_id').text)

		except Exception:
			logger.exception('get_movie_dblist err')