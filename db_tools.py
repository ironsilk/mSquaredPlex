import mysql.connector.errors
from utils import connect_mysql, close_mysql, create_db, check_table, logger, deconvert_imdb_id, update_many
from settings import table_columns
from torr_service.torr_tools import get_torr_quality
from tmdb_omdb_tools import get_tmdb, get_omdb

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


def check_in_my_torrents(new_movies):
    conn, cursor = connect_mysql()
    q = "SELECT * FROM {table} WHERE torr_id IN ('{values}')".format(
        table='my_torrents',
        values="','".join([str(x['id']) for x in new_movies])
    )
    cursor.execute(q)
    already_in_db = [x['torr_id'] for x in cursor.fetchall()]
    for movie in new_movies:
        if movie['id'] in already_in_db:
            movie['torr_already_seen'] = True
        else:
            movie['torr_already_seen'] = False
    return new_movies


def update_my_torrents_db(items):
    ids = [{'torr_id': x['id']} for x in items if not x['torr_already_seen']]
    update_many(ids, 'my_torrents')


def retrieve_bulk_from_dbs(items):
    logger.info("Getting IMDB TMDB and OMDB metadata...")
    # Connections
    conn, cursor = connect_mysql()
    return [retrieve_one_from_dbs(item, cursor) for item in items]


def retrieve_one_from_dbs(item, cursor):
    """(self, vColor, vCount, vTitle, vYear, vIMDBid, vPoster, vResolution, vGenre, vRated, vCountry, vRuntime, vIMDBScore,
    vTMDBScore, vRottenTScore, vMetaCScore, vPlot, vTrailer, vDirector, vActors, vSize, vFreeL, vFLISid, vMyScore,
    vMyScoreDate)"""
    # ID
    imdb_id_number = deconvert_imdb_id(item['imdb'])
    # Search in local_db
    imdb_keys = get_movie_IMDB(imdb_id_number, cursor)
    # Search online if TMDB, OMDB not found in local DB
    if imdb_keys['hit_tmdb'] != 1:
        tmdb = get_tmdb(imdb_id_number)
        if tmdb['hit_tmdb'] == 1:
            imdb_keys.update(tmdb)
            # Update db
            update_many([tmdb], 'tmdb_data')
    if imdb_keys['hit_omdb'] != 1:
        omdb = get_omdb(imdb_id_number)
        if omdb['hit_omdb'] == 1:
            imdb_keys.update(omdb)
            # Update db
            update_many([omdb], 'omdb_data')
    return {**item, **imdb_keys}


def get_movie_IMDB(imdb_id, cursor=None):
    if not cursor:
        conn, cursor = connect_mysql()
    q = f"""SELECT a.*, b.numVotes, b.averageRating, e.title, c.*, d.* FROM title_basics a
    left join title_ratings b on a.tconst = b.tconst
    left join tmdb_data c on a.tconst = c.imdb_id
    left join omdb_data d on a.tconst = d.imdb_id
    left join title_akas e on a.tconst = e.titleId
    where a.tconst = {imdb_id} AND e.isOriginalTitle = 1
    """
    cursor.execute(q)
    return cursor.fetchone()


if __name__ == '__main__':
    check_db()
