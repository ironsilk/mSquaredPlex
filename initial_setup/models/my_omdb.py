from utils import logger
import omdb as omdb_api
from initial_setup.models.movie import Movie
from settings import OMDB_API_KEY


class OMDB(Movie):

    def __init__(self, id_imdb):
        Movie.__init__(self, id_imdb)
        self.genre = None
        self.lang = None
        self.imdb_score = None
        self.rott_score = None
        self.meta_score = None
        self.rated = None
        self.awards = None
        self.director = None
        self.actors = None
        self.apikey_omdb = OMDB_API_KEY

    def get_data(self):
        logger.info('get_data {}'.format(self.id_imdb))

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


if __name__ == '__main__':
    tmdb = OMDB('tt0903624')
    tmdb.get_data()
