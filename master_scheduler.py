from datetime import datetime
import os

from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR, EVENT_JOB_SUBMITTED
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

update_imdb_db()
scheduler.add_job(update_imdb_db, 'cron', day=1, hour=2, name='update_imdb_db', coalesce=True)
scheduler.add_job(get_tmdb_data, 'interval', seconds=20, name='get_tmdb_data', coalesce=True)
scheduler.add_job(get_omdb_data, 'interval', seconds=5, name='get_omdb_data', coalesce=True)
scheduler.add_job(sync_my_imdb, 'interval', seconds=11, name='sync_my_imdb', coalesce=True)


def execution_listener(event):
    # print(event)
    if event.exception:
        print('The job crashed')
    else:
        # print('The job executed successfully')
        # check that the executed job is the first job
        job = scheduler.get_job(event.job_id)
        if job.name == 'get_tmdb_data':
            print('Running the second job')
            # lookup the second job (assuming it's a scheduled job)
            jobs = scheduler.get_jobs()
            print(jobs)
            # second_job = next((j for j in jobs if j.name == 'second_job'), None)
            # if second_job:
                # run the second job immediately
                # second_job.modify(next_run_time=datetime.datetime.utcnow())
            # else:
                # job not scheduled, add it and run now
                # scheduler.add_job(second_job_func, args=(...), kwargs={...},
                #                 name='second_job')


def job_starts(event):
    job = scheduler.get_job(event.job_id)
    if job.name == 'get_omdb_data':
        print('our job started')
    return event
    
scheduler.add_listener(job_starts, EVENT_JOB_SUBMITTED)
scheduler.add_listener(execution_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)


scheduler.start()
