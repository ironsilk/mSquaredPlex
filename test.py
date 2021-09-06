import os
from pprint import pprint

import imdb
import pandas as pd
import sqlalchemy
import re
from utils import get_email_by_tgram_id, deconvert_imdb_id
from dotenv import load_dotenv

load_dotenv()

context = update = None
soap_pattern = re.compile(": Season \d+:")

DB_URI = "mysql://{u}:{p}@{hp}/{dbname}?charset=utf8".format(
    u=os.getenv('MYSQL_MYIMDB_USER'),
    p=os.getenv('MYSQL_MYIMDB_PASS'),
    hp=':'.join([os.getenv('MYSQL_MYIMDB_HOST'), os.getenv('MYSQL_MYIMDB_PORT')]),
    dbname=os.getenv('MYSQL_MYIMDB_DB_NAME'),
)

df = pd.read_csv(r'C:\Users\mihai\Downloads\NetflixViewingHistory.csv')
df['Date'] = pd.to_datetime(df['Date'])
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

try:
    ia = imdb.IMDb('s3', DB_URI)
except sqlalchemy.exc.OperationalError:
    ia = imdb.IMDb()

identified_movies = []
soap_or_unidentified = 0
user = 'mike'


for movie in df[:100]:
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
                item = {
                    'seen_date': movie['Date'],
                    'imdb_id': deconvert_imdb_id(res[0]['id']),
                    'user': user,
                }
                if has_ratings:
                    item['rating_status'] = 'rated externally'
                    item['my_score'] = movie['ratings']
                identified_movies.append(item)
            else:
                soap_or_unidentified += 1
            # return {x.data for x in movies}
        except Exception as e:
            pass

print(f"Found {soap_or_unidentified} episodes watched")
print(f"Identified {len(identified_movies)} movies")
pprint(identified_movies)












