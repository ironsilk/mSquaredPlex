import datetime
import os
import re
import xml.etree.ElementTree as ET

import omdb.api as omdb_api
import tmdbsimple as tmdb_api

from utils import logger, convert_imdb_id

TMDB_API_KEY = os.getenv('TMDB_API_KEY')
OMDB_API_KEY = os.getenv('OMDB_API_KEY')


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
            logger.debug('get_movie_dblist err')


class TMDB(Movie):

    def __init__(self, id_imdb, type_tmdb, id_tmdb, search_title=None, search_year=None):
        Movie.__init__(self, id_imdb)
        self.genre = None
        self.url = None
        self.lang = None
        self.runtime = None
        self.ovrw = None
        self.poster = None
        self.trailer = None
        self.cast = None
        self.director = None
        self.backdrops = None
        self.type_tmdb = type_tmdb
        self.id_tmdb = id_tmdb
        self.apikey_tmdb = TMDB_API_KEY
        self.search_title = search_title
        self.search_year = search_year
        self.search_result = None

    def get_data(self):
        logger.debug('get_data {0} / {1} {2}'.format(self.id_imdb, self.type_tmdb, self.id_tmdb))
        tmdb_api.API_KEY = self.apikey_tmdb

        if self.id_imdb == '':
            if self.id_tmdb != '':
                if 'movie' in self.type_tmdb:
                    self.tmdb_movie()
                elif 'tv' in self.type_tmdb:
                    self.tmdb_tv()
                else:
                    print('err tmdb - could not detemine tmdb id (movie or tv) for: {0}'.format(self.id_tmdb))
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
                    logger.debug('0 results for movie - id imdb:{}'.format(self.id_imdb))
                    if find.tv_results:
                        self.id_tmdb = find.tv_results[0]['id']
                        self.tmdb_tv()
                    else:
                        logger.debug('0 results for tv shows - id imdb:{}'.format(self.id_imdb))
                        return
            except Exception:
                logger.debug('err tmdb - id=tt. Response is: {}'.format(response))
                return

        if self.country is not None:
            cntry_dict = {'United States of America': 'USA', 'United Kingdom': 'UK', 'GB': 'UK', 'FR': 'France',
                          'US': 'USA', 'DE': 'Germany', 'RU': 'Russia'}
            for country_long, country_short in cntry_dict.items():
                self.country = re.sub(r'\b%s\b' % country_long, country_short, self.country)

        if self.lang is not None:
            lang_dict = {'en': 'English', 'es': 'Espanol', 'fr': 'Francais', 'de': 'Deutsch', 'pl': 'Polski',
                         'shqip': 'Albanian', 'bi': 'Bislama', 'ky': 'Kirghiz', 'tl': 'Tagalog', 'ny': 'Chichewa',
                         'st': 'Southern Sotho', 'xh': 'Xhosa', 'hi': 'Hindi', 'tn': 'Tswana'}
            for lang_short, lang_long in lang_dict.items():
                self.lang = re.sub(r'\b%s\b' % lang_short.lower(), lang_long, self.lang)
            self.lang = self.lang.title()

    def tmdb_movie(self):
        logger.debug('tmdb_movie {0}'.format(self.id_tmdb))

        self.type_tmdb = 'movie'

        try:
            movie = tmdb_api.Movies(self.id_tmdb)
            response = movie.info()
        # print response
        except Exception:
            logger.debug('could not load JSON from tmdb for movie id:{}'.format(self.id_tmdb))
            return

        try:
            self.id_imdb = movie.imdb_id
        except Exception:
            logger.debug('')

        try:
            self.url = 'https://www.themoviedb.org/movie/{0}'.format(movie.id)
        except Exception:
            logger.debug('')

        try:
            self.title = movie.title
        except Exception:
            logger.debug('')

        try:
            self.year = movie.release_date[:4]
        except Exception:
            logger.debug('')

        # obtine doar primele 4 genre
        try:
            if movie.genres:
                genre = movie.genres[0]['name']
                for x in range(3):
                    try:
                        genre = '{0}, {1}'.format(genre, movie.genres[x + 1]['name'])
                    except:
                        break
                self.genre = genre
            else:
                logger.debug('no "genre" value available')
        except Exception:
            logger.debug('')

        # obtine doar primele 4 country
        try:
            if movie.production_countries:
                country = movie.production_countries[0]['name']
                for x in range(3):
                    try:
                        country = '{0}, {1}'.format(country, movie.production_countries[x + 1]['name'])
                    except:
                        break
                self.country = country
            else:
                logger.debug('no "production_countries" value available')
        except Exception:
            logger.debug('')

        # obtine doar primele 4 lang
        try:
            if movie.spoken_languages:
                lang = movie.spoken_languages[0]['name']
                if lang == '' or lang == '??????':
                    lang = movie.spoken_languages[0]['iso_639_1']
                    logger.debug('weird lang - iso_639_1 code is:{}'.format(lang))
                for x in range(3):
                    try:
                        if movie.spoken_languages[x + 1]['name'] != '':
                            lang = '{0}, {1}'.format(lang, movie.spoken_languages[x + 1]['name'])
                        else:
                            lang = '{0}, {1}'.format(lang, movie.spoken_languages[x + 1]['iso_639_1'])
                            logger.debug('weird lang - iso_639_1 code is:{}'.format(lang))
                    except:
                        break
                self.lang = lang
            else:
                logger.debug('no "languages" value available')
        except Exception:
            logger.debug('')

        try:
            self.score = movie.vote_average
        except Exception:
            logger.debug('')

        try:
            self.runtime = movie.runtime
        except Exception:
            logger.debug('')

        try:
            self.ovrw = movie.overview.replace('\n', '').replace('\r', '')
        except Exception:
            logger.debug('')

        try:
            self.poster = 'https://image.tmdb.org/t/p/w300_and_h450_bestv2{0}'.format(movie.poster_path)
        except Exception:
            logger.debug('')

        try:
            response = movie.videos()
        except Exception:
            logger.debug('')

        try:
            for x in movie.results:
                if x['type'] == 'Trailer' and x['site'] == 'YouTube':
                    if x['key'] is not None:
                        self.trailer = 'https://www.youtube.com/watch?v={0}'.format(x['key'])
                    break
        except Exception:
            logger.debug('')

        try:
            response = movie.credits()
        except Exception:
            logger.debug('')

        try:
            temp_cast = ''
            for s in movie.cast[:5]:
                temp_cast = '{0}, {1}'.format(temp_cast, s['name'].encode('utf-8'))
            self.cast = temp_cast[2:]
        except Exception:
            logger.debug('')

        try:
            for s in movie.crew:
                if s['job'] == 'Director':
                    self.director = s['name']
        except Exception:
            logger.debug('')

        try:
            response = movie.images()
        except Exception:
            logger.debug('')

        try:
            backdrops = []
            for s in movie.backdrops:
                backdrops.append('http://image.tmdb.org/t/p/w1280{0}'.format(s['file_path']))
            self.backdrops = backdrops
        except Exception:
            logger.debug('')

    def tmdb_tv(self):
        logger.debug('tmdb_tv {0}'.format(self.id_tmdb))

        self.type_tmdb = 'tv'

        try:
            tv = tmdb_api.TV(self.id_tmdb)
            response = tv.info()
        except Exception:
            logger.debug('')

        try:
            self.url = 'https://www.themoviedb.org/tv/{0}'.format(self.id_tmdb)
        except Exception:
            logger.debug('')

        try:
            self.title = tv.name
        except Exception:
            logger.debug('')

        try:
            self.year = tv.first_air_date[:4]
        except Exception:
            logger.debug('')

        try:
            if tv.genres:
                genre = tv.genres[0]['name']
                for x in range(3):
                    try:
                        genre = '{0}, {1}'.format(genre, tv.genres[x + 1]['name'])
                    except:
                        break
                self.genre = genre
            else:
                logger.debug('no "genre" value available')
        except Exception:
            logger.debug('')

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
                            country = '{0}, {1}'.format(country, tv.origin_country[x + 1]['name'])
                        else:
                            country = '{0}, {1}'.format(country, tv.origin_country[x + 1])
                    except:
                        break
                self.country = country
            else:
                logger.debug('no "origin_country" value available')
        except Exception:
            logger.debug('')

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
                            lang = '{0}, {1}'.format(lang, tv.languages[x + 1]['name'])
                        else:
                            lang = '{0}, {1}'.format(lang, tv.languages[x + 1])
                    except:
                        break
                self.lang = lang
            else:
                logger.debug('no "languages" value available')
        except Exception:
            logger.debug('')

        try:
            self.score = tv.vote_average
        except Exception:
            logger.debug('')

        try:
            self.ovrw = tv.overview.replace('\n', '').replace('\r', '')
        except Exception:
            logger.debug('')

        try:
            self.poster = 'https://image.tmdb.org/t/p/w300_and_h450_bestv2{0}'.format(tv.poster_path)
        except Exception:
            logger.debug('')

        try:
            response = tv.videos()
        except Exception:
            logger.debug('')

        try:
            for x in tv.results:
                if x['type'] == 'Trailer' and x['site'] == 'YouTube':
                    if x['key'] is not None:
                        self.trailer = 'https://www.youtube.com/watch?v={0}'.format(x['key'])
                    break
        except Exception:
            logger.debug('')

        try:
            response = tv.credits()
        except Exception:
            logger.debug('')

        try:
            temp_cast = ''
            for s in tv.cast[:5]:
                temp_cast = '{0}, {1}'.format(temp_cast, s['name'].encode('utf-8'))
            self.cast = temp_cast[2:]
        except Exception:
            logger.debug('')

        try:
            for s in tv.crew:
                if s['job'] == 'Director':
                    self.director = s['name']
        except Exception:
            logger.debug('')

        try:
            response = tv.images()
        except Exception:
            logger.debug('')

        try:
            backdrops = []
            for s in tv.backdrops:
                backdrops.append('http://image.tmdb.org/t/p/w1280{0}'.format(s['file_path']))
            self.backdrops = backdrops
        except Exception:
            logger.debug('')

    def tmdb_search(self):
        logger.debug('tmdb_search movie title & year: {0} {1}'.format(self.search_title, self.search_year))
        try:
            search = tmdb_api.Search()
            response = search.movie(query=self.search_title)
        # print response
        except Exception:
            logger.debug('')

        try:
            for s in search.results:
                if self.search_year is not None and self.search_year == int(s['release_date'][:4]):
                    self.title = s['title']
                    self.id_tmdb = s['id']
                    self.year = int(s['release_date'][:4])
                    self.score = s['popularity']
                    self.search_result = 'based on title and year'
                    break
            if self.id_tmdb is None:
                self.title = s['title']
                self.id_tmdb = s['id']
                self.year = int(s['release_date'][:4])
                self.score = s['popularity']
                self.search_result = 'based only on title'
        except Exception:
            logger.debug('')


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
        logger.debug('get_data {}'.format(self.id_imdb))

        try:
            omdb_api.set_default('apikey', self.apikey_omdb)
            raw_omdb = omdb_api.imdbid(self.id_imdb)
        except Exception:
            logger.debug('could not load JSON from omdb for id:{}'.format(self.id_imdb))
            return

        if 'title' in raw_omdb:
            self.title = raw_omdb['title']
        else:
            logger.debug('no "title" in omdb json')

        if 'year' in raw_omdb:
            self.year = raw_omdb['year']
        else:
            logger.debug('no "year" in omdb json')

        if 'country' in raw_omdb:
            self.country = raw_omdb['country']
        else:
            logger.debug('no "country" in omdb json')

        if 'genre' in raw_omdb:
            self.genre = raw_omdb['genre']
        else:
            logger.debug('no "genre" in omdb json')

        if 'language' in raw_omdb:
            self.lang = raw_omdb['language']
        else:
            logger.debug('no "language" in omdb json')

        if 'ratings' in raw_omdb:
            for data in raw_omdb['ratings']:
                if data['source'] == 'Internet Movie Database':
                    self.imdb_score = data['value'][:-3]
                elif data['source'] == 'Rotten Tomatoes':
                    self.rott_score = data['value'][:-1]
                elif data['source'] == 'Metacritic':
                    self.meta_score = data['value'][:-4]
        else:
            logger.debug('no "ratings" in omdb json')

        if 'rated' in raw_omdb:
            self.rated = raw_omdb['rated']
        else:
            logger.debug('no "rated" in omdb json')

        if 'awards' in raw_omdb:
            self.awards = raw_omdb['awards']
        else:
            logger.debug('no "awards" in omdb json')

        if 'director' in raw_omdb:
            self.director = raw_omdb['director']
        else:
            logger.debug('no "director" in omdb json')

        if 'actors' in raw_omdb:
            self.actors = raw_omdb['actors']
        else:
            logger.debug('no "actors" in omdb json')


def get_tmdb(idd):
    tmdb = TMDB(convert_imdb_id(idd), '', '')
    tmdb.get_data()

    if all(v is None for v in [tmdb.country, tmdb.lang, tmdb.ovrw, tmdb.score, tmdb.trailer]):
        hit = False
    else:
        hit = True

    item = {
        'imdb_id': idd,
        'country': tmdb.country,
        'lang': tmdb.lang,
        'ovrw': tmdb.ovrw,
        'tmdb_score': tmdb.score,
        'trailer_link': tmdb.trailer,
        'poster': tmdb.poster,
        'last_update_tmdb': datetime.datetime.now(),
        'hit_tmdb': hit,
    }
    return item


def get_omdb(idd):
    omdb = OMDB(convert_imdb_id(idd))
    omdb.get_data()
    try:
        rated = float(omdb.rated)
    except (ValueError, TypeError):
        rated = None

    if all(v is None for v in [omdb.awards, omdb.country, omdb.lang, omdb.meta_score, omdb.rott_score, omdb.score]):
        hit = False
    else:
        hit = True

    item = {
        'imdb_id': idd,
        'awards': omdb.awards,
        'country': omdb.country,
        'lang': omdb.lang,
        'meta_score': omdb.meta_score,
        'rated': rated,
        'rott_score': omdb.rott_score,
        'omdb_score': omdb.score,
        'last_update_omdb': datetime.datetime.now(),
        'hit_omdb': hit,
    }
    return item


if __name__ == '__main__':
    from pprint import pprint
    pprint(get_omdb(2088003))
    pprint(get_tmdb(2088003))
