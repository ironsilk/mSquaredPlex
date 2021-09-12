from telegram.ext import CallbackContext

from bot_utils import _title_header
from utils import setup_logger, update_many, get_unrated_movies, Movie, get_movie_details

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
        for item in unrated_movies:
            # Get info about movie and make caption
            pkg = get_movie_details(item)
            if pkg:
                title = _title_header(pkg['title'], pkg['originalTitle'], pkg['startYear'])
                # Create message and send
                caption = f"Hi! Looks like you've watched:\n" \
                          f"{title}" \
                          f"If you want to rate it, click below!\n" \
                          f"🦧 /RateTitle{item['imdb_id']}"
                context.bot.send_message(chat_id=item['user_id'], text=caption)
                update_movie_rated_status(item, 'notification sent')
            else:
                logger.error("")


def update_movie_rated_status(item, new_status):
    item = dict(item)
    item['rating_status'] = new_status
    update_many([item], Movie, [Movie.id])


if __name__ == '__main__':
    bot_rate_titles(None)
