from telegram.ext import CallbackContext

from bot_utils import get_movie_from_all_databases, make_movie_reply, get_image, _title_header
from utils import setup_logger, connect_mysql, get_my_imdb_users, update_many

logger = setup_logger("BotRateTitles")


def bot_rate_titles(context: CallbackContext) -> None:
    """
    Gets unrated movies from the database and pings the users to
    rate them.
    :param context:
    :return:
    """
    # Get unrated movies
    unrated_movies = get_unrated_movies()
    if unrated_movies:
        logger.info(f"Got {len(unrated_movies)} unrated movies.")
        users = get_my_imdb_users()
        for item in unrated_movies:
            # Get user chat id
            chat_id = [x['telegram_chat_id'] for x in users if x['email'] == item['user']][0]
            # Get info about movie and make caption
            pkg = get_movie_from_all_databases(item['imdb_id'])
            title = _title_header(pkg['title'], pkg['originalTitle'], pkg['startYear'])
            # Create message and send
            caption = f"Hi! Looks like you've watched:\n" \
                      f"{title}" \
                      f"If you want to rate it, click below!\n" \
                      f"🦧 /RateTitle{item['imdb_id']}"
            context.bot.send_message(chat_id=chat_id, text=caption)
            update_movie_rated_status(item, 'notification sent')


def get_unrated_movies():
    conn, cursor = connect_mysql()
    q = f"SELECT * FROM my_movies WHERE my_score is NULL and rating_status is NULL"
    cursor.execute(q)
    return cursor.fetchall()


def update_movie_rated_status(item, new_status):
    item['rating_status'] = new_status
    update_many([item], 'my_movies')


if __name__ == '__main__':
    from pprint import pprint

    bot_rate_titles(None)
