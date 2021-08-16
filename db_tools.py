import mysql.connector.errors

from utils import connect_mysql, close_mysql, create_db, check_table, logger, deconvert_imdb_id
from settings import table_columns, DB_URI, custom_settings
from torr_tools import get_torr_quality
from imdb import IMDb

"""
Database tools
https://github.com/dlwhittenbury/MySQL_IMDb_Project
"""


def check_db():
    logger.info("Checking DB at service startup")
    try:
        conn, cursor = connect_mysql()
    except mysql.connector.errors.ProgrammingError:  # if db doesn't exist, create it
        create_db('plex_buddy')
        conn, cursor = connect_mysql()
    # Check all tables defined in settings.py, table_columns.
    for table, columns in table_columns.items():
        check_table(
            cursor,
            table=table,
            columns=list(columns.keys()),
            column_types=columns,
        )
    close_mysql(conn, cursor)
    logger.info("All tables OK.")


def check_in_my_movies(new_movies):
    """
    checks if passed new movies are already in database.
    :param new_movies: dict, returned from FL API
    :return: filtered dict
    """

    def get_intersections(new, old):
        """
        Makes intersections with database,
        adds already_in_db and better_quality parameters.
        :param new:
        :param old:
        :return:
        """
        lst = []
        for new_m in new:
            d = {
                'already_in_db': False,
                'better_quality': False,
            }
            if new_m['imdb'] in [x['imdb_id'] for x in old]:
                old_quality = [x['resolution'] for x in old if x['imdb_id'] == new_m['imdb']][0]
                new_quality = get_torr_quality(new_m['name'])
                d['already_in_db'] = True
                if int(new_quality) > int(old_quality):
                    d['better_quality'] = True
            lst.append({**new_m, **d})
        return lst
    conn, cursor = connect_mysql()
    q = "SELECT * FROM {table} WHERE imdb_id IN ('{values}')".format(
        table='my_movies',
        values="','".join([x['imdb'] for x in new_movies])
    )
    cursor.execute(q)
    already_in_db = cursor.fetchall()
    new = get_intersections(new_movies, already_in_db)
    # Filter out new movies already in database and where quality is the same or poorer
    new = [x for x in new if x['already_in_db'] is False or x['better_quality'] is True]

    return new


def retrieve_bulk_from_dbs(items):
    # Connection to IMDB
    ia = IMDb('s3', DB_URI)
    items = [retrieve_one_from_dbs(item, ia) for item in items]


def retrieve_one_from_dbs(item, ia):
    """(self, vColor, vCount, vTitle, vYear, vIMDBid, vPoster, vResolution, vGenre, vRated, vCountry, vRuntime, vIMDBScore,
    vTMDBScore, vRottenTScore, vMetaCScore, vPlot, vTrailer, vDirector, vActors, vSize, vFreeL, vFLISid, vMyScore,
    vMyScoreDate)"""
    imdb_id = deconvert_imdb_id(item['imdb'])
    # Search in IMDB


def get_movie_IMDB(imdb_id, ia=IMDb('s3', DB_URI)):
    # ia = IMDb('s3', DB_URI)
    # ia = IMDb()
    results = ia.search_movie(imdb_id)
    for result in results:
        print(result.movieID, result)

    matrix = results[0]
    ia.update(matrix)
    print(matrix.keys())
    return results


if __name__ == '__main__':
    x = get_movie_IMDB('tt0903624')[0]
    print(x.keys())
    print(x['original title'])


    """
    SELECT a.*, b.numVotes, b.averageRating, e.title, c.*, d.* FROM title_basics a
    left join title_ratings b on a.tconst = b.tconst
    left join tmdb_data c on a.tconst = c.imdb_id
    left join omdb_data d on a.tconst = d.imdb_id
    left join title_akas e on a.tconst = e.titleId
    where a.tconst = 488 AND e.isOriginalTitle = 1
    """