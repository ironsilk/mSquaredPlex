import xml.etree.ElementTree as ET
from utils import logger


class Movie:

    def __init__(self, id_imdb):
        self.id_list = []
        self.id_imdb = id_imdb
        self.title = None
        self.year = None
        self.country = None
        self.score = None

    def get_movie_dblist(self, xml_path):
        try:
            XMLtree = ET.parse(xml_path)
            XMLroot = XMLtree.getroot()
            for child in XMLroot:
                self.id_list.append(child.find('imdb_id').text)

        except Exception:
            logger.exception('get_movie_dblist err')
