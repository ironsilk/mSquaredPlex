from datetime import datetime
import os
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
# from db_services.refresh_imdb_db import update_imdb_db  # IMDB_DB_REFRESH_INTERVAL
# from db_services.refresh_tmdb_db import get_tmdb_data  # no sleep
# from db_services.refresh_omdb_db import get_omdb_data  # sleep 1 hr between runs
# from db_services.sync_my_imdb_db import sync_my_imdb  # MY_IMDB_REFRESH_INTERVAL
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

def update_imdb_db():
    print('update_imdb_db! The time is: %s' % datetime.now())

def get_tmdb_data():
    print('get_tmdb_data! The time is: %s' % datetime.now())

def get_omdb_data():
    print('get_omdb_data! The time is: %s' % datetime.now())

def sync_my_imdb():
    print('sync_my_imdb! The time is: %s' % datetime.now())

# ENV variables
TIMEZONE = os.getenv('TIMEZONE')
IMDB_DB_REFRESH_INTERVAL = int(os.getenv('IMDB_DB_REFRESH_INTERVAL'))
MY_IMDB_REFRESH_INTERVAL = int(os.getenv('MY_IMDB_REFRESH_INTERVAL'))

DB_URI = "mysql://{u}:{p}@{hp}/{dbname}?charset=utf8".format(
    u=os.getenv('MYSQL_USER'),
    p=os.getenv('MYSQL_PASS'),
    hp=':'.join([os.getenv('MYSQL_HOST'), os.getenv('MYSQL_PORT')]),
    dbname=os.getenv('MYSQL_DB_NAME'),
)

jobstores = {
    'default': SQLAlchemyJobStore(url=DB_URI)
}

scheduler = BlockingScheduler(jobstores=jobstores, timezone=TIMEZONE)
print(scheduler.print_jobs())
print(scheduler.get_jobs())
