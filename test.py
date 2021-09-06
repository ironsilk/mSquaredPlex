import pandas as pd


df = pd.read_csv(r'C:\Users\mihai\Downloads\NetflixViewingHistory.csv')
df['Date'] = pd.to_datetime(df['Date'])
has_ratings = 'ratings' in df.columns
df = df.to_dict('records')