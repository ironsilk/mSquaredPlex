from telegram import Update
from telegram.ext import CallbackContext
import io
import pandas as pd


def csv_upload_handler(update: Update, context: CallbackContext):
    file = context.bot.getFile(update.message.document.file_id)
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
    for movie in df:
        # get from imdb, see if it's a movie and upload.
        # Save a count in order to feed it back to the user.
        pass

