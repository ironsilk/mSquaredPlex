from functools import wraps
from time import time
import logging
import mysql.connector as cnt
from settings import custom_settings

logger = logging.getLogger('PlexService')


def convert_imdb_id(id):
    '''
    289992 turns into tt0289992
    :param id:
    :return:
    '''
    if len(str(id)) < 7:
        return 'tt' + str(id).zfill(7)
    else:
        return 'tt' + str(id)


def deconvert_imdb_id(imdb_id):
    '''
    tt0289992 turns into 289992
    :param imdb_id:
    :return:
    '''
    return imdb_id.replace('tt', '').lstrip('0')


def connect_mysql():
    # Connects to mysql and returns cursor
    sql_conn = cnt.connect(host=custom_settings['mysql_host'], port=custom_settings['mysql_port'],
                           database=custom_settings['mysql_db_name'],
                           user=custom_settings['mysql_user'], password=custom_settings['mysql_pass'])
    return sql_conn, sql_conn.cursor(dictionary=True)


def close_mysql(conn, cursor):
    conn.close()
    return


def create_db(name):
    sql_conn = cnt.connect(
        host=custom_settings['mysql_host'], port=custom_settings['mysql_port'],
        user=custom_settings['mysql_user'], password=custom_settings['mysql_pass'])
    sql_conn.cursor().execute("CREATE DATABASE {x}".format(x=name))
    sql_conn.close()


def check_table(cursor, table, columns, column_types):
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
        primary_key = columns.pop(0)
        del column_types[primary_key]
        q = f'''
        CREATE TABLE `{table}` (
        `{primary_key}` int(11) NOT NULL,
        PRIMARY KEY (`{primary_key}`) KEY_BLOCK_SIZE=1024
        ) ENGINE=MyISAM DEFAULT CHARSET=utf8mb4 ROW_FORMAT=COMPRESSED KEY_BLOCK_SIZE=8;
        '''
        cursor.execute(q)
        for col in columns:
            try:
                query = "ALTER TABLE {table} ADD {column} {col_type}".format(table=table, column=col,
                                                                             col_type=column_types[col])
                cursor.execute(query)
            except Exception as e:
                logger.error(e)
                raise e
        logger.info("Done! Table created.")


def insert_sql(chunk, table, columns):
    '''
    Inserts chunk into sql, if it fails
    it fallsback to row insert and errors get logged into
    a local error log file.
    '''
    conn, cursor = connect_mysql()
    placeholder = ", ".join(["%s"] * len(columns))
    stmt = "INSERT into `{table}` ({columns}) values ({values});".format(table=table, columns=",".join(columns),
                                                                         values=placeholder)
    try:
        cursor.executemany(stmt, chunk)
        conn.commit()
    except Exception as e:
        logger.error("Error {e} inserting chunk into mysql, falling back to atomic insert".format(e=e))
        for item in chunk:
            atomic_insert_sql(item, conn, cursor, table, columns)
    close_mysql(conn, cursor)


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


def update_one(update_columns, update_values, condition_col, condition_value, table, conn=None, cursor=None):
    # Update_columns and update values must be lists with same length such as:
    # new_name=Somename, new_age=Someage etc.
    # Condition col will mostly be the primary key and cond values will be the ids.
    if not cursor:
        conn, cursor = connect_mysql()
    set_statement = ", ".join(
        ['''`{col}` = "{value}"'''.format(col=col, value=val) for col, val in zip(update_columns, update_values)])
    stmt = '''UPDATE `{table}` SET {set_statement} WHERE `{condition_col}` = '{value}' '''.format(
        table=table,
        set_statement=set_statement,
        condition_col=condition_col,
        value=condition_value)
    try:
        cursor.execute(stmt)
        conn.commit()
    except cnt.errors.IntegrityError as e:
        logger.error('Got {e}'.format(e=e))


def update_many(data_list=None, mysql_table=None):
    """
    Updates a mysql table with the data provided. If the key is not unique, the
    data will be inserted into the table.

    The dictionaries must have all the same keys due to how the query is built.

    Param:
        data_list (List):
            A list of dictionaries where the keys are the mysql table
            column names, and the values are the update values
        mysql_table (String):
            The mysql table to be updated.
    """

    # Connection and Cursor
    conn, cur = connect_mysql()

    query = ""
    values = []

    for data_dict in data_list:

        if not query:
            columns = ', '.join(['`{0}`'.format(k) for k in data_dict])
            duplicates = ', '.join(['{0}=VALUES({0})'.format(k) for k in data_dict])
            place_holders = ', '.join(['%s'.format(k) for k in data_dict])
            query = f"INSERT INTO {mysql_table} ({columns}) VALUES ({place_holders})"
            query = f"{query} ON DUPLICATE KEY UPDATE {duplicates}"

        v = list(data_dict.values())
        values.append(v)

    try:
        cur.executemany(query, values)
    except Exception as e:
        try:
            print("MySQL Error [%d]: %s" % (e.args[0], e.args[1]))
        except IndexError:
            print("MySQL Error: %s" % str(e))

        conn.rollback()
        return False

    conn.commit()
    cur.close()
    conn.close()


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