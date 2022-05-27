import os

from telegram import Bot
import asyncio
from utils import setup_logger, update_many, Movie, get_movie_details, \
    get_unrated_movies, _title_header

logger = setup_logger("BotRateTitles")

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')


async def bot_rate_titles() -> None:
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
                          f"🦧 /RateTitle_{item['imdb_id']}"
                bot = Bot(token=TELEGRAM_TOKEN)
                await bot.send_message(chat_id=item['user_id'], text=caption)
                update_movie_rated_status(item, 'notification sent')
            else:
                logger.error("")


def update_movie_rated_status(item, new_status):
    item = dict(item)
    item['rating_status'] = new_status
    update_many([item], Movie, Movie.id)


def run_ratetitle_dog():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(bot_rate_titles())


if __name__ == '__main__':
    run_ratetitle_dog()


