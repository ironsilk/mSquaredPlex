import logging
import os
import re
from functools import wraps

from telegram import (
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Update,
)
from telegram.ext import Updater, MessageHandler, Filters, CallbackContext, ConversationHandler, CallbackQueryHandler, \
    CommandHandler
from transmission_rpc.error import TransmissionError

from bot_utils import make_movie_reply, get_telegram_users, update_torr_db, \
    exclude_torrents_from_watchlist, get_excluded_resolutions, \
    invite_friend, get_movie_from_all_databases, search_imdb_title, check_one_in_my_movies, get_imdb_id_by_trgram_id, \
    add_to_watchlist
from bot_watchlist import bot_watchlist_routine, update_watchlist_item_status, get_torrents_for_imdb_id
from bot_rate_title import bot_rate_titles
from utils import update_many, deconvert_imdb_id, send_torrent, compose_link, check_db_plexbuddy, convert_imdb_id

TELEGRAM_AUTH_TEST_PATH = os.getenv('TELEGRAM_AUTH_TEST_PATH')
TELEGRAM_AUTH_APPROVE = os.getenv('TELEGRAM_AUTH_APPROVE')
TELEGRAM_IMDB_RATINGS = os.getenv('TELEGRAM_IMDB_RATINGS')
TELEGRAM_WATCHLIST_ROUTINE_INTERVAL = int(os.getenv('TELEGRAM_WATCHLIST_ROUTINE_INTERVAL'))
TELEGRAM_RATE_ROUTINE_INTERVAL = int(os.getenv('TELEGRAM_RATE_ROUTINE_INTERVAL'))

# Other info:
# https://github.com/Ambro17/AmbroBot
# https://github.com/notPlasticCat/Library-Genesis-Bot/blob/main/LibGenBot/__main__.py

# Job Queue
# https://github.com/python-telegram-bot/python-telegram-bot/wiki/Extensions-%E2%80%93-JobQueue
# https://github.com/python-telegram-bot/python-telegram-bot/blob/master/examples/timerbot.py

# Enable logging
logging.basicConfig(
    format='[%(asctime)s] {%(filename)s:%(lineno)d} [%(name)s] [%(levelname)s] --> %(message)s', level=logging.INFO
)

logger = logging.getLogger('MovieTimeBot')

# Stages
CHOOSE_TASK, IDENTIFY_MOVIE, CHOOSE_MULTIPLE, CHOOSE_ONE, CONFIRM_REDOWNLOAD_ACTION, SEARCH_FOR_TORRENTS, \
DOWNLOAD_TORRENT, CHECK_RIDDLE_RESPONSE, CHECK_EMAIL, GIVE_IMDB, CHECK_IMDB, SUBMIT_RATING, \
WATCHLIST_NO_TORR, = range(13)

# Keyboards
menu_keyboard = [
    ["📥 Download a movie"],
    ["📈 Check progress"],
]
bool_keyboard = [
    ['Yes'],
    ['No']
]
movie_selection_keyboard = [
    ['Yes'],
    ['No'],
    ['Exit'],
]
rate_keyboard = [
    ['1', '2'],
    ['3', '4'],
    ['5', '6'],
    ['7', '8'],
    ['9', '10'],
    ["I've changed my mind"]
]

# Get users from db
USERS = get_telegram_users()


def auth_wrap(f):
    @wraps(f)
    def wrap(update: Update, context: CallbackContext):
        user = update.effective_user['id']
        if user in USERS.keys():
            # Ok boss
            result = f(update, context)
            return result
        else:
            # Check this mofo
            update.effective_message.reply_photo(
                photo=open(TELEGRAM_AUTH_TEST_PATH, 'rb'),
                caption="Looks like you're new here. Answer correctly and you may enter.",
            )
            return CHECK_RIDDLE_RESPONSE

    return wrap


def check_riddle(update: Update, context: CallbackContext):
    if update.message.text.lower() == 'mellon':
        update.effective_message.reply_photo(
            photo=open(TELEGRAM_AUTH_APPROVE, 'rb'),
            caption="Welcome! Just a few more steps to configure your preferences. "
                    "First, please type in your email so that we can add you "
                    "to our PLEX users.",
        )
        return CHECK_EMAIL
    else:
        update.effective_message.reply_text("Sorry boi, ur welcome to try again.")
        return CHECK_RIDDLE_RESPONSE


def check_email(update: Update, context: CallbackContext):
    # Invite to PLEX server
    email_invite = invite_friend(update.message.text)
    if email_invite:
        message = "Great! An invitation for PLEX has been sent to your email.\n"
    else:
        message = "Looks like this email is already in our PLEX users database. " \
                  "If this is not the case, please contact the admin.\n\n"

    # Continue to IMDB stuff
    context.user_data['new_user'] = {
        'telegram_chat_id': update.message.chat_id,
        'telegram_name': update.effective_user.first_name,
        'email': update.message.text,
        'email_newsletters': True,
        'scan_watchlist': False,

    }
    message += "Would you like to connect you IMDB account? " \
               "In this way we'll be able to pull your movie " \
               "ratings and warn you when you'll search for a movie " \
               "you've already seen.\n" \
               "We'll also scan your watchlist periodically and notify you " \
               "when we'll be able to download any of the titles there.\n" \
               "In the future we're planning to be able to " \
               "give ratings here and transfer them to IMDB."
    update.effective_message.reply_text(message, reply_markup=ReplyKeyboardMarkup(bool_keyboard,
                                                                                  one_time_keyboard=True,
                                                                                  resize_keyboard=True,
                                                                                  ))
    return GIVE_IMDB


def give_imdb(update: Update, context: CallbackContext):
    if update.message.text == 'Yes':
        update.effective_message.reply_photo(
            photo=open(TELEGRAM_IMDB_RATINGS, 'rb'),
            caption="I'll need you to go to your IMDB account and copy here your user ID, like the one in the photo, "
                    "ur77571297. Also make sure that your Ratings are PUBLIC and so is your Watchlist (10 pages max).\n"
                    "If this is too much, just type 'fuck it' and skip this step.",
        )
        return CHECK_IMDB
    else:
        return register_user(update, context)


def check_imdb(update: Update, context: CallbackContext):
    if update.message.text.lower() != 'fuck it':
        context.user_data['new_user']['scan_watchlist'] = True
        context.user_data['new_user']['imdb_id'] = ''.join([x for x in update.message.text if x.isdigit()])
    return register_user(update, context)


def register_user(update: Update, context: CallbackContext):
    global USERS
    # Update user to database
    update_many([context.user_data['new_user']], 'users')
    USERS = get_telegram_users()
    update.effective_message.reply_text("Ok, that's it. I'll take care of the rest, from now on "
                                        "anytime you type something i'll be here to help you out. Enjoy!")
    return start(update, context)


def wrong_input(update: Update, context: CallbackContext):
    update.effective_message.reply_text("Wrong input, please try again.")
    return CHECK_EMAIL


@auth_wrap
def start(update: Update, context: CallbackContext) -> int:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    update.message.reply_markdown_v2(
        f"Hi {user.mention_markdown_v2()}\!\n"
        fr"Please select one of the options or type /help for more options\.",
        reply_markup=ReplyKeyboardMarkup(menu_keyboard, one_time_keyboard=True, resize_keyboard=True),
    )
    return CHOOSE_TASK


@auth_wrap
def choose_task(update: Update, context: CallbackContext) -> int:
    if update.message.text == menu_keyboard[0][0]:
        message = 'Great, give me an IMDB id, a title or an IMDB link.'
        update.message.reply_text(message)
        return IDENTIFY_MOVIE

    elif update.message.text == menu_keyboard[1][0]:
        message = 'Not implemented yet'
        update.message.reply_text(message)

    return ConversationHandler.END


@auth_wrap
def parse_imdb_id(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("Just a sec until we get data about this title...")
    # We need number so filter out the number from the user input:
    imdb_id = ''.join([x for x in update.message.text if x.isdigit()]).lstrip('0')

    # Get IMDB data
    pkg = get_movie_from_all_databases(imdb_id)
    context.user_data['pkg'] = pkg
    context.user_data['more_options'] = False

    message, image = make_movie_reply(pkg)
    update.effective_message.reply_photo(
        photo=image,
        caption=message,
        reply_markup=ReplyKeyboardMarkup(movie_selection_keyboard,
                                         one_time_keyboard=True,
                                         resize_keyboard=True,
                                         ),
    )
    return CHOOSE_ONE


@auth_wrap
def parse_imdb_text(update: Update, context: CallbackContext) -> int:
    # https://www.w3resource.com/mysql/string-functions/mysql-soundex-function.php
    # https://stackoverflow.com/questions/2602252/mysql-query-string-contains
    update.message.reply_text("Just a sec until we get data about this title...")
    # Is it a link?
    try:
        imdb_id = re.search(r"[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)",
                            update.message.text).group(0)

        # We need number so filter out the number from the user input:
        imdb_id = ''.join([x for x in imdb_id if x.isdigit()]).lstrip('0')

        # Get IMDB data
        pkg = get_movie_from_all_databases(imdb_id)
        context.user_data['pkg'] = pkg

        message, image = make_movie_reply(pkg)
        update.effective_message.reply_photo(
            photo=image,
            caption=message,
            reply_markup=ReplyKeyboardMarkup(movie_selection_keyboard,
                                             one_time_keyboard=True,
                                             resize_keyboard=True,
                                             ),
        )
        return CHOOSE_ONE
    except AttributeError:
        # Yes but wrong link or no match
        if 'https://' in update.message.text:
            update.effective_message.reply_text("Couldn't find the specified ID in the link, are you"
                                                "sure it's an IMDB link? Try pasting only the ID, as in"
                                                "`tt0903624`.")
            return IDENTIFY_MOVIE
        else:
            # Test for title
            movies = search_imdb_title(update.message.text)
            #  movies = []
            context.user_data['potential_titles'] = movies

            return choose_multiple(update, context)


@auth_wrap
def choose_multiple(update: Update, context: CallbackContext) -> int:
    movies = context.user_data['potential_titles']
    if movies:
        if type(movies) == str:
            update.effective_message.reply_text("We're having trouble with our IMDB API, please"
                                                "insert an IMDB ID or paste a link.")
            return IDENTIFY_MOVIE
        movie = movies.pop(0)
        # Check again if we can find it
        pkg = get_movie_from_all_databases(movie['id'])
        # context.user_data['pkg'] = pkg
        if pkg:
            context.user_data['pkg'] = pkg

            message, image = make_movie_reply(pkg)
            update.effective_message.reply_photo(
                photo=image,
                caption=message,
                reply_markup=ReplyKeyboardMarkup(movie_selection_keyboard,
                                                 one_time_keyboard=True,
                                                 resize_keyboard=True,
                                                 ),
            )
            return CHOOSE_ONE
        else:
            return choose_multiple(update, context)
    else:
        update.effective_message.reply_text("Couldn't find the specified movie,"
                                            "Try pasting the IMDB id or a link"
                                            "`tt0903624`.")
        return IDENTIFY_MOVIE


@auth_wrap
def accept_reject_title(update: Update, context: CallbackContext) -> int:
    if update.message.text == 'Yes':
        return check_movie_status(update, context)
    elif update.message.text == 'No':
        if context.user_data['potential_titles']:
            update.effective_message.reply_text("Ok, trying next hit...")
            return choose_multiple(update, context)
        else:
            update.effective_message.reply_text("These were all the hits.")
            return bail(update, context)
    elif update.message.text == 'Exit':
        return bail(update, context)


@auth_wrap
def check_movie_status(update: Update, context: CallbackContext) -> int:
    movie = context.user_data['pkg']
    # Check if you've already seen it and send info
    if movie['already_in_my_movies']:
        message = f"You know this movie."
        if 'my_score' in movie.keys():
            message += f"\nYour score: {movie['my_score']}"
        if 'seen_date' in movie.keys():
            message += f"\nAnd you've seen it on {movie['seen_date']}"
        update.message.reply_text(message)
        if movie['torr_result']:
            message = f"Looks like the movie is also downloaded in {movie['resolution']}p\n" \
                      f"Torrent status: {movie['torr_status']}\n" \
                      f"Would you still like to proceed to download?"
        else:
            message = f"\nWould you still like to proceed to download?"

        update.effective_message.reply_html(message, reply_markup=ReplyKeyboardMarkup(bool_keyboard,
                                                                                      one_time_keyboard=True,
                                                                                      resize_keyboard=True,
                                                                                      ))
        return CONFIRM_REDOWNLOAD_ACTION
    else:
        return search_for_torrents(update, context)


@auth_wrap
def confirm_redownload_action(update: Update, context: CallbackContext) -> int:
    if update.message.text == 'Yes':
        return search_for_torrents(update, context)
    else:
        return bail(update, context)


@auth_wrap
def search_for_torrents(update: Update, context: CallbackContext) -> int:
    update.message.reply_text('Searching for available torrents...')
    torrents = get_torrents_for_imdb_id(context.user_data['pkg']['imdb'])
    torrents = sorted(torrents, key=lambda k: k['size'])
    if torrents:
        context.user_data['pkg']['torrents'] = sorted(torrents, key=lambda k: k['size'])
        keyboard = [[]]
        # Check if we need to filter excluded resolutions
        if 'from_watchlist' in context.user_data.keys():
            movie_id = deconvert_imdb_id(torrents[0]['imdb'])
            excluded_resolutions = get_excluded_resolutions(movie_id, update.effective_user['id'])
            torrents = [x for x in torrents if x['id'] not in excluded_resolutions]
        for pos, item in enumerate(torrents):
            pos += 1  # exclude 0
            btn_text = (
                f"🖥 Q: {str(item['resolution'])}"
                f"🗳 S: {str(round(item['size'] / 1000000000, 2))} GB"
                f"🌱 S/P: {str(item['seeders'])}/{str(item['leechers'])}"
                # f"📤 [DOWNLOAD]\n"
            )
            btn = InlineKeyboardButton(btn_text, callback_data=item['id'])
            keyboard.append([btn])
        # Add button for None
        keyboard.append([InlineKeyboardButton('None, thanks', callback_data=0)])
        update.message.reply_text(
            f"Please select one of the torrents",
            reply_markup=InlineKeyboardMarkup(keyboard, one_time_keyboard=True),
        )
        return DOWNLOAD_TORRENT
    else:
        # aici
        update.message.reply_text(
            "We couldn't find any torrents for this title.\n"
            "Would you like to add it to your watchlist?",
            reply_markup=ReplyKeyboardMarkup(bool_keyboard, one_time_keyboard=True, resize_keyboard=True),
        )
        return WATCHLIST_NO_TORR


@auth_wrap
def add_to_watchlist_no_torrent(update: Update, context: CallbackContext) -> int:
    if update.message.text == 'Yes':
        # Try to get user's IMDB id if he has any
        try:
            imdb_id = get_imdb_id_by_trgram_id(update.effective_user['id'])
        except Exception as e:
            logger.warning(f"Error upon retrieving IMDB id for user with tgram_id {update.effective_user['id']} "
                           f"might not have any. Error: {e}")
            imdb_id = None
        if 'torrents' not in context.user_data['pkg'].keys():
            add_to_watchlist(deconvert_imdb_id(context.user_data['pkg']['imdb']), imdb_id, 'new')
        else:
            add_to_watchlist(deconvert_imdb_id(context.user_data['pkg']['imdb']), imdb_id, 'new',
                             [x['id'] for x in context.user_data['pkg']['torrents']])
        message = "Added to watchlist! What's next?"
    else:
        message = "Ok, what would you like to do next?"
    update.message.reply_text(
        message,
        reply_markup=ReplyKeyboardMarkup(menu_keyboard, one_time_keyboard=True, resize_keyboard=True),
    )
    return CHOOSE_TASK


@auth_wrap
def download_torrent(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()
    if query.data != '0':
        query.edit_message_text(text=f"Thanks, sending download request...")
        # Send download request
        try:
            torr = [x for x in context.user_data['pkg']['torrents'] if query.data == str(x['id'])][0]
            # Send torrent to daemon
            torr_client_resp = send_torrent(compose_link(query.data))
            # Update torrent DB
            update_torr_db(torr, torr_client_resp, update.effective_user['id'])
            message = f"Download started, have a great day!"
        except TransmissionError as e:
            logger.error(f"Error on torrent send: {e}")
            message = f"Download failed, please check logs and try again."
        query.edit_message_text(text=message)
        return ConversationHandler.END
    else:
        if 'from_watchlist' in context.user_data.keys():
            query.edit_message_text(text="Ok, i'll remove these torrent options from future watchlist alerts "
                                         "regarding this movie.")
            return exclude_res_from_watchlist(update, context)
        else:
            # query.edit_message_text(text="Shit")
            print(update.message)
            update.effective_message.reply_text('Would you like to add it to your watchlist?',
                                                reply_markup=ReplyKeyboardMarkup(bool_keyboard,
                                                                                 one_time_keyboard=True,
                                                                                 resize_keyboard=True))
            return WATCHLIST_NO_TORR


@auth_wrap
def bail(update: Update, context: CallbackContext) -> int:
    if update.message.text.lower() == 'suka' or 'exit':
        context.user_data.clear()
        update.message.reply_text("Ok, have a great day!")
        return ConversationHandler.END
    update.message.reply_text("Please re-enter your search query or type 'suka' to exit")
    context.user_data.clear()
    return IDENTIFY_MOVIE


@auth_wrap
def go_back(update, context, message):
    update.message.reply_text(message)
    context.user_data.clear()
    context.user_data['dont_greet'] = True
    return choose_task(update, context)


@auth_wrap
def help_command(update: Update, context: CallbackContext) -> None:
    """Displays info on how to use the bot."""

    watchlist_status = 'MONITORING' if USERS[update.effective_user.id]['scan_watchlist'] == 1 else 'NOT MONITORING'
    email_status = 'RECEIVING' if USERS[update.effective_user.id]['email_newsletters'] else 'NOT RECEIVING'
    update.message.reply_text("Type anything for the bot to start.\n\n"
                              f"Right now we are {watchlist_status} your watchlist. "
                              f"Type /change_watchlist "
                              "to reverse the status.\n\n"
                              f"Right now you are {email_status} the email newsletters. Type /change_newsletter "
                              "to reverse the status.\n\n"
                              "If you want to change your email address or your imdb ID type /update_user "
                              "and we'll ask you to retake the login process. Once started, you must complete "
                              "the entire process.")


@auth_wrap
def change_watchlist_command(update: Update, context: CallbackContext) -> None:
    pkg = USERS[update.effective_user.id]
    if pkg['scan_watchlist'] == 0:
        pkg['scan_watchlist'] = 1
    else:
        pkg['scan_watchlist'] = 0
    update_many([pkg], 'users')
    update.message.reply_text("Updated your watchlist preferences.")


@auth_wrap
def change_newsletter_command(update: Update, context: CallbackContext) -> None:
    pkg = USERS[update.effective_user.id]
    if pkg['email_newsletters'] == 0:
        pkg['email_newsletters'] = 1
    else:
        pkg['email_newsletters'] = 0
    update_many([pkg], 'users')
    update.message.reply_text("Updated your newsletter preferences.")


@auth_wrap
def update_user(update: Update, context: CallbackContext) -> None:
    update.message.reply_text('Type anything to get started.')
    del USERS[update.effective_user.id]


@auth_wrap
def watchlist_entry(update: Update, context: CallbackContext) -> int:
    context.user_data['pkg'] = {
        'imdb': int(update.message.text.replace('/WatchMatch', '')),
    }
    context.user_data['from_watchlist'] = True
    update.message.reply_text('Watchlist entry')
    return search_for_torrents(update, context)


@auth_wrap
def remove_watchlist_entry(update: Update, context: CallbackContext) -> int:
    movie_id = int(update.message.text.replace('/UnWatchMatch', ''))
    update_watchlist_item_status(movie_id, update.effective_user['id'], 'closed')
    update.message.reply_text("Done, no more watchlist updates for this movie.")
    return ConversationHandler.END


@auth_wrap
def exclude_res_from_watchlist(update: Update, context: CallbackContext) -> int:
    torrents = context.user_data['pkg']['torrents']
    movie_id = deconvert_imdb_id(torrents[0]['imdb'])
    exclude_torrents_from_watchlist(movie_id, update.effective_user['id'], [x['id'] for x in torrents])
    update.callback_query.edit_message_text(text="Removed these torrent quality for future recommendations "
                                                 "on this title.")
    return ConversationHandler.END


@auth_wrap
def rate_title_entry(update: Update, context: CallbackContext) -> int:
    context.user_data['pkg'] = {
        'imdb': int(update.message.text.replace('/RateTitle', '')),
    }

    message = f"Please choose a rating."
    update.effective_message.reply_html(message, reply_markup=ReplyKeyboardMarkup(rate_keyboard,
                                                                                  one_time_keyboard=True,
                                                                                  resize_keyboard=True,
                                                                                  ))
    return SUBMIT_RATING


@auth_wrap
def submit_rating(update: Update, context: CallbackContext) -> int:
    if update.message.text in [str(x) for x in list(range(1, 11))]:
        # Got rating
        item = check_one_in_my_movies(context.user_data['pkg']['imdb'])
        item['rating_status'] = 'rated in telegram'
        item['my_score'] = int(update.message.text)
        update_many([item], 'my_movies')
        update.effective_message.reply_text(f"Ok, great! Here's a link if you also want to rate it on IMDB:\n"
                                            f"https://www.imdb.com/title/"
                                            f"{convert_imdb_id(context.user_data['pkg']['imdb'])}/")
        return ConversationHandler.END

    elif update.message.text == "I've changed my mind":
        item = check_one_in_my_movies(context.user_data['pkg']['imdb'])
        item['rating_status'] = 'refused to rate'
        update_many([item], 'my_movies')
        update.effective_message.reply_text("Ok, no worries! I won't bother you about this title anymore.\n"
                                            "Have a great day!")
        return ConversationHandler.END
    else:
        update.effective_message.reply_text("Please choose an option from the keyboard.")
        return SUBMIT_RATING


@auth_wrap
def end(update, context, message):
    return ConversationHandler.END


def main() -> None:
    check_db_plexbuddy()
    """Start the bot."""
    # Create the Updater and pass it your bot's token.
    updater = Updater("1940395527:AAF1Orhib5d6QvtIMtiOS8WaHWZfN8IrI2Y")

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(Filters.regex(r'^/WatchMatch\d+$'), watchlist_entry),
            MessageHandler(Filters.regex(r'^/UnWatchMatch\d+$'), remove_watchlist_entry),
            MessageHandler(Filters.regex(r'^/RateTitle\d+$'), rate_title_entry),
            MessageHandler(Filters.text, start),
        ],
        states={
            CHOOSE_TASK: [
                MessageHandler(
                    Filters.text, choose_task
                )
            ],
            IDENTIFY_MOVIE: [
                MessageHandler(
                    Filters.regex('^([tT]{2})?\d+$'), parse_imdb_id
                ),
                MessageHandler(
                    Filters.text, parse_imdb_text
                ),
            ],
            CHOOSE_MULTIPLE: [
                MessageHandler(
                    Filters.text, choose_multiple
                )
            ],
            CHOOSE_ONE: [
                MessageHandler(
                    Filters.text, accept_reject_title
                )
            ],
            CONFIRM_REDOWNLOAD_ACTION: [
                MessageHandler(
                    Filters.text, confirm_redownload_action
                )
            ],
            SEARCH_FOR_TORRENTS: [
                MessageHandler(
                    Filters.text, search_for_torrents
                )
            ],
            DOWNLOAD_TORRENT: [
                CallbackQueryHandler(
                    download_torrent
                )
            ],
            CHECK_RIDDLE_RESPONSE: [
                MessageHandler(
                    Filters.text, check_riddle
                )
            ],
            CHECK_EMAIL: [
                MessageHandler(
                    Filters.regex('[^@]+@[^@]+\.[^@]+'), check_email
                ),
                MessageHandler(
                    Filters.text, wrong_input,
                ),
            ],
            GIVE_IMDB: [
                MessageHandler(
                    Filters.text, give_imdb,
                ),
            ],
            CHECK_IMDB: [
                MessageHandler(
                    Filters.regex('^[u]?[r]?\d+$'), check_imdb
                ),
                MessageHandler(
                    Filters.regex('fuck it'), check_imdb
                ),
                MessageHandler(
                    Filters.regex('Fuck it'), check_imdb
                ),
                MessageHandler(
                    Filters.text, wrong_input
                ),
            ],
            SUBMIT_RATING: [
                MessageHandler(
                    Filters.text, submit_rating
                ),
            ],
            WATCHLIST_NO_TORR: [
                MessageHandler(
                    Filters.text, add_to_watchlist_no_torrent
                ),
            ],
        },
        fallbacks=[MessageHandler(Filters.text, end)],
        per_message=False
    )
    dispatcher.add_handler(CommandHandler('help', help_command))
    dispatcher.add_handler(CommandHandler('change_watchlist', change_watchlist_command))
    dispatcher.add_handler(CommandHandler('change_newsletter', change_newsletter_command))
    dispatcher.add_handler(CommandHandler('update_user', update_user))
    dispatcher.add_handler(conv_handler)

    # Start the Bot
    updater.start_polling()
    job_queue = updater.job_queue
    job_queue.run_repeating(bot_watchlist_routine, interval=TELEGRAM_WATCHLIST_ROUTINE_INTERVAL * 60, first=5)
    job_queue.run_repeating(bot_rate_titles, interval=TELEGRAM_WATCHLIST_ROUTINE_INTERVAL * 60, first=5)

    updater.idle()


if __name__ == '__main__':
    main()
