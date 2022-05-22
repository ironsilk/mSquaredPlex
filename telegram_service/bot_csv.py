import io
import re

import imdb
import pandas as pd
import sqlalchemy
from telegram.ext import CallbackContext

from utils import get_user_by_tgram_id, deconvert_imdb_id, update_many, get_movie_details, get_my_movie_by_imdb, \
    get_user_movies, DB_URI, Movie

soap_pattern = re.compile(": Season \d+:")


async def csv_upload_handler(context: CallbackContext):
    file_id = context.job.context['file']
    tgram_user = context.job.context['user']
    send_notifications = context.job.context['send_notifications']
    file = await context.bot.getFile(file_id)
    # Create an in-memory file
    f = io.BytesIO()
    await file.download(out=f)
    # Pointer is at the end of the file so reset it to 0.
    f.seek(0)
    # To pd.df
    df = pd.read_csv(f)
    try:
        df['Date'] = pd.to_datetime(df['Date'])
        has_ratings = 'Ratings' in df.columns
        df = df.to_dict('records')
    except Exception as e:
        # send error to user
        await context.bot.send_message(f"Encountered some problems with the CSV you gave me.\n"
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
    user = get_user_by_tgram_id(tgram_user)
    for movie in df:
        if soap_pattern.search(movie['Title']):
            soap_or_unidentified += 1
        else:
            try:
                movies = ia.search_movie(movie['Title'], _episodes=False)
                res = []
                for x in movies:
                    if 'kind' in x.data.keys():
                        if x.data['kind'] == 'movie':
                            x.data['id'] = x.movieID
                            res.append(x.data)
                            break
                if res:
                    my_movie = get_my_movie_by_imdb(deconvert_imdb_id(res[0]['id']), user['telegram_chat_id'])
                    if not my_movie:
                        item = {
                            'seen_date': movie['Date'].to_pydatetime(),
                            'imdb_id': deconvert_imdb_id(res[0]['id']),
                            'user_id': user['telegram_chat_id'],
                        }
                        if has_ratings:
                            item['rating_status'] = 'rated externally'
                            item['my_score'] = movie['Ratings']
                        if not send_notifications:
                            item['rating_status'] = 'refused to rate'
                        identified_movies.append(item)
                    else:
                        pass
                else:
                    soap_or_unidentified += 1
            except Exception as e:
                raise e
                pass
    update_many(identified_movies, Movie, Movie.id)
    await context.bot.send_message(text=f"CSV update successful!\n"
                                        f"Out of {len(df)} entries in your CSV file, "
                                        f"{len(identified_movies)} were movies while "
                                        f"{soap_or_unidentified} were either soap episodes, "
                                        f"series or likewise. The rest were already in your database "
                                        f"({len(df) - len(identified_movies) - soap_or_unidentified})",
                                   chat_id=tgram_user)


def csv_download_handler(context: CallbackContext):
    tgram_user = context.job.context['user']
    user = get_user_by_tgram_id(tgram_user)
    # Get movies from my_movies:
    my_movies = get_user_movies(user)
    enhanced = []
    # Get titles for each movie :)
    if my_movies:
        for movie in my_movies:
            enhanced.append(get_movie_details(movie))
        df = pd.DataFrame(enhanced)
        # Create an in-memory file
        f = io.BytesIO()
        # Write to buffer
        df.to_csv(f)
        # Pointer is at the end of the file so reset it to 0.
        f.seek(0)
        context.bot.send_document(
            chat_id=tgram_user,
            document=f,
            filename='MoviesExport.csv',
            caption="Here's your requested movie DB export.\n"
                    "Have a great day!"
        )
    else:
        context.bot.send_message(
            chat_id=tgram_user,
            text="Looks like you don't have any movies yet. Nothing to fill that CSV with."
        )


