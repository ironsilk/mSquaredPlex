import io
import os
import re

import imdb
import pandas as pd
import sqlalchemy
from telegram.ext import CallbackContext

from utils import get_email_by_tgram_id, deconvert_imdb_id, update_many
from bot_utils import check_one_in_my_movies

soap_pattern = re.compile(": Season \d+:")

DB_URI = "mysql://{u}:{p}@{hp}/{dbname}?charset=utf8".format(
    u=os.getenv('MYSQL_MYIMDB_USER'),
    p=os.getenv('MYSQL_MYIMDB_PASS'),
    hp=':'.join([os.getenv('MYSQL_MYIMDB_HOST'), os.getenv('MYSQL_MYIMDB_PORT')]),
    dbname=os.getenv('MYSQL_MYIMDB_DB_NAME'),
)


def csv_upload_handler(context: CallbackContext):
    file_id = context.job.context['file']
    tgram_user = context.job.context['user']
    send_notifications = context.job.context['send_notifications']
    file = context.bot.getFile(file_id)
    # Create an in-memory file
    f = io.BytesIO()
    file.download(out=f)
    # Pointer is at the end of the file so reset it to 0.
    f.seek(0)
    # To pd.df
    df = pd.read_csv(f)
    try:
        df['Date'] = pd.to_datetime(df['Date'])
        has_ratings = 'ratings' in df.columns
        df = df.to_dict('records')
    except Exception as e:
        # send error to user
        context.bot.send_message(f"Encountered some problems with the CSV you gave me.\n"
                                 f"Make sure you have 'Title' and 'Date' as required columns "
                                 f"and the optional 'ratings' column.\n"
                                 f"Err description: {e}")
        return

    try:
        ia = imdb.IMDb('s3', DB_URI)
    except sqlalchemy.exc.OperationalError:
        ia = imdb.IMDb()

    identified_movies = []
    soap_or_unidentified = 0
    user = get_email_by_tgram_id(tgram_user)

    for movie in df:
        if soap_pattern.search(movie['Title']):
            soap_or_unidentified += 1
        else:
            try:
                movies = ia.search_movie(movie['Title'], _episodes=False)
                res = []
                for x in movies:
                    if x.data['kind'] == 'movie':
                        x.data['id'] = x.movieID
                        res.append(x.data)
                if res:
                    my_movie = check_one_in_my_movies(deconvert_imdb_id(res[0]['id']))
                    if not my_movie:
                        item = {
                            'seen_date': movie['Date'].to_pydatetime(),
                            'imdb_id': deconvert_imdb_id(res[0]['id']),
                            'user': user,
                        }
                        if has_ratings:
                            item['rating_status'] = 'rated externally'
                            item['my_score'] = movie['ratings']
                        if not send_notifications:
                            item['rating_status'] = 'refused to rate'
                        identified_movies.append(item)
                    else:
                        pass
                else:
                    soap_or_unidentified += 1
            except Exception as e:
                pass
    update_many(identified_movies, 'my_movies')
    context.bot.send_message(text=f"CSV update successful!\n"
                                  f"Out of {len(df)} entries in your CSV file, "
                                  f"{len(identified_movies)} were movies while the "
                                  f"rest of {soap_or_unidentified} were either soap episodes, "
                                  f"series or likewise. The rest were already in your database "
                                  f"({len(df) - len(identified_movies) - soap_or_unidentified})",
                             chat_id=tgram_user)
