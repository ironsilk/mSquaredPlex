from functools import wraps
from time import time
import logging
import mysql.connector as cnt
from settings import custom_settings

logger = logging.getLogger('PlexService')


def connect_mysql():
    # Connects to mysql and returns cursor
    sql_conn = cnt.connect(host=custom_settings['mysql_host'], port=custom_settings['mysql_port'],
                           database=custom_settings['mysql_db_name'],
                           user=custom_settings['mysql_user'], password=custom_settings['mysql_pass'])
    return sql_conn, sql_conn.cursor(dictionary=True)


def close_mysql(conn, cursor):
    conn.close()
    return


def check_tables(conn, cursor):
    logger.info("Checking tables at service startup")
    # Check posts table
    table = custom_settings['mysql_table_root'] + '_hashes'
    check_table(table, cursor, post_columns, post_column_types)
    close_mysql(conn, cursor)


def check_table(table, cursor, columns, column_types):
    db = custom_settings['mysql_db_name']
    q = '''
    SELECT table_name FROM information_schema.tables WHERE table_name = '{table}' AND table_schema = '{db_name}'
    '''.format(db_name=db, table=table)
    cursor.execute(q)
    result = cursor.fetchone()
    if result:
        pass
    else:
        logger.info("Table '{table}' does not exist, creating...".format(table=table))
        q = '''
        CREATE TABLE `{table}` (
        `id` int(11) NOT NULL AUTO_INCREMENT,
        PRIMARY KEY (`id`) KEY_BLOCK_SIZE=1024
        ) ENGINE=MyISAM AUTO_INCREMENT=0 DEFAULT CHARSET=utf8mb4 ROW_FORMAT=COMPRESSED KEY_BLOCK_SIZE=8;
        '''.format(table=table)
        cursor.execute(q)
        for col in columns:
            try:
                query = "ALTER TABLE {table} ADD {column} {col_type}".format(table=table, column=col,
                                                                             col_type=column_types[col])
                cursor.execute(query)
            except Exception as e:
                pass
        logger.info("Done! Table created.")


def atomic_insert_sql(item, conn, cursor, table, columns):
    """
    Inserts into mysql one row at a time and returns the ID.
    """
    placeholder = ", ".join(["%s"] * len(columns))
    stmt = "INSERT into `{table}` ({columns}) values ({values});".format(table=table,
                                                                         columns=",".join(columns),
                                                                         values=placeholder)
    try:
        cursor.execute(stmt, item)
        conn.commit()
        r = {
            'status': "Ok",
            'id': cursor.lastrowid
        }
    except Exception as e:
        r = {
            'status': e,
            'id': None
        }
    return r


def timing(f):
    @wraps(f)
    def wrap(*args, **kw):
        ts = time()
        result = f(*args, **kw)
        te = time()
        print('func:%r took: %2.4f sec' % \
              (f.__name__, te - ts))
        return result

    return wrap