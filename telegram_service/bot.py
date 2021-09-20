import logging
import os
import re
from functools import wraps

from telegram import (
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Update, )
from telegram.ext import Updater, MessageHandler, Filters, CallbackContext, ConversationHandler, CallbackQueryHandler, \
    CommandHandler, DispatcherHandlerStop
from transmission_rpc.error import TransmissionError

from bot_csv import csv_upload_handler, csv_download_handler
from bot_get_progress import get_progress
from bot_rate_title import bot_rate_titles
from bot_utils import make_movie_reply, get_telegram_users, update_torr_db, \
    exclude_torrents_from_watchlist, get_excluded_resolutions, \
    invite_friend, get_movie_from_all_databases, search_imdb_title, add_to_watchlist
from bot_watchlist import bot_watchlist_routine, update_watchlist_item_status, get_torrents_for_imdb_id
from utils import update_many, deconvert_imdb_id, send_torrent, compose_link, check_database, convert_imdb_id, \
    get_my_movie_by_imdb, Movie, User, get_user_by_tgram_id

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_AUTH_TEST_PATH = os.getenv('TELEGRAM_AUTH_TEST_PATH')
TELEGRAM_AUTH_APPROVE = os.getenv('TELEGRAM_AUTH_APPROVE')
TELEGRAM_IMDB_RATINGS = os.getenv('TELEGRAM_IMDB_RATINGS')
TELEGRAM_NETFLIX_PNG = os.getenv('TELEGRAM_NETFLIX_PNG')
TELEGRAM_RESET_PNG = os.getenv('TELEGRAM_RESET_PNG')
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

# State definitions for top level conversation
CHOOSE_TASK, REGISTER_USER, DOWNLOAD_MOVIE, CHECK_PROGRESS, UPLOAD_ACTIVITY, RATE_TITLE = range(6)

# State definitions  DOWNLOAD_MOVIE
CHOOSE_MULTIPLE, CHOOSE_ONE, CONFIRM_REDOWNLOAD_ACTION, SEARCH_FOR_TORRENTS, \
DOWNLOAD_TORRENT, WATCHLIST_NO_TORR = range(6, 12)

# State definitions for CHECK_PROGRESS
DOWNLOAD_PROGRESS = 12

# State definitions for UPLOAD_ACTIVITY
NETFLIX_CSV, RATE_OR_NOT_TO_RATE = 13, 14

# State definitions for DOWNLOAD_ACTIVITY
DOWNLOAD_CSV = 15

# State definitions for RATE_TITLE
SUBMIT_RATING = 16

# State definitions for REGISTER_USER
CHECK_EMAIL, GIVE_IMDB, CHECK_IMDB = range(17, 20)

# State definitions for aux functions
RESET_CONVERSATION = 21

# Keyboards
menu_keyboard = [
    ["📥 Download a movie"],
    ["📈 Check download progress"],
    ["❤☠🤖 Upload Netflix activity", '💾 Download my movies']
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
USERS = []


def auth_wrap(f):
    @wraps(f)
    def wrap(update: Update, context: CallbackContext):
        print(f"Wrapped {f.__name__}", )
        user = update.effective_user['id']
        if user in USERS.keys():
            # Ok boss
            result = f(update, context)
            print(result)
            return result
        else:
            # Check this mofo
            update.effective_message.reply_photo(
                photo=open(TELEGRAM_AUTH_TEST_PATH, 'rb'),
                caption="Looks like you're new here. Answer correctly and you may enter.",
            )
            return REGISTER_USER

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
        return REGISTER_USER


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
                    "If this is too much, just type 'fuck it' and skip this step.\n"
                    "https://www.imdb.com/",
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
    update_many([context.user_data['new_user']], User, User.telegram_chat_id)
    USERS = get_telegram_users()
    update.effective_message.reply_text("Ok, that's it. I'll take care of the rest, from now on "
                                        "anytime you type something i'll be here to help you out. Enjoy!\n"
                                        "Type /help to find out more.")
    return start(update, context)


def wrong_input(update: Update, context: CallbackContext):
    update.effective_message.reply_text("Wrong input, please try again.")
    return CHECK_EMAIL


def wrong_input_imdb(update: Update, context: CallbackContext):
    update.effective_message.reply_text("Wrong input, please try again.")
    return CHECK_IMDB


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
        return DOWNLOAD_MOVIE

    elif update.message.text == menu_keyboard[1][0]:
        update.effective_message.reply_text('Ok, retrieving data... (might be slow sometimes)')
        context.user_data['download_progress'] = 0
        return get_download_progress(update, context)

    elif update.message.text == menu_keyboard[2][0]:
        update.message.reply_photo(photo=open(TELEGRAM_NETFLIX_PNG, 'rb'),
                                   caption="Ok, follow the instructions, "
                                           "hit `Download all` and upload here the resulting .csv.\n"
                                           "You may add any other records to "
                                           "the CSV, given that you don't change the column names.\n"
                                           "If you want to also add ratings, create an extra column "
                                           "named 'ratings' and it will be picked up.\n"
                                           "Any overlapping ratings/seen dates will be overwritten. However, "
                                           "IMDB ratings, seen dates and PLEX seen dates will have prevalence.\n"
                                           "☢️☢️!! If these titles are not rated in the CSV you'll receive "
                                           "notifications to rate all of them.\n\n"
                                           "Choose Yes/No",
                                   reply_markup=ReplyKeyboardMarkup(bool_keyboard, one_time_keyboard=True,
                                                                    resize_keyboard=True))
        return UPLOAD_ACTIVITY
    elif update.message.text == menu_keyboard[2][1]:
        update.message.reply_text("Ok, we've started the process, we'll let you know once it's done.")
        return download_csv(update, context)

    return break_level(update, context)


@auth_wrap
def parse_imdb_id(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("Just a sec until we get data about this title...")
    # We need number so filter out the number from the user input:
    imdb_id = ''.join([x for x in update.message.text if x.isdigit()]).lstrip('0')

    # Get IMDB data
    pkg = get_movie_from_all_databases(imdb_id, update.effective_user['id'])
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
        pkg = get_movie_from_all_databases(imdb_id, update.effective_user['id'])
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
            return DOWNLOAD_MOVIE
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
            return DOWNLOAD_MOVIE
        movie = movies.pop(0)
        # Check again if we can find it
        pkg = get_movie_from_all_databases(movie['id'], update.effective_user['id'])
        # context.user_data['pkg'] = pkg
        if pkg:
            context.user_data['pkg'] = pkg
            # https://stackoverflow.com/questions/39571474/send-long-message-with-photo-on-telegram-with-php-bot#:~:text=I%20need%20send%20to%20telegram,caption%20has%20200%20character%20limit.
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
        return DOWNLOAD_MOVIE


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
            return break_level(update, context)
    elif update.message.text == 'Exit':
        return break_level(update, context)


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
        return break_level(update, context)


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
            user = get_user_by_tgram_id(update.effective_user['id'])
        except Exception as e:
            logger.warning(f"Error upon retrieving IMDB id for user with tgram_id {update.effective_user['id']} "
                           f"might not have any. Error: {e}")
            user = None
        if 'torrents' not in context.user_data['pkg'].keys():
            add_to_watchlist(deconvert_imdb_id(context.user_data['pkg']['imdb']), user, 'new')
        else:
            add_to_watchlist(deconvert_imdb_id(context.user_data['pkg']['imdb']), user, 'new',
                             [x['id'] for x in context.user_data['pkg']['torrents']])
        message = "Added to watchlist!"
        update.message.reply_text(message)

    return break_level(update, context)


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
        return CHOOSE_TASK
    else:
        if 'from_watchlist' in context.user_data.keys():
            query.edit_message_text(text="Ok, i'll remove these torrent options from future watchlist alerts "
                                         "regarding this movie.")
            return exclude_res_from_watchlist(update, context)
        else:
            update.effective_message.reply_text('Would you like to add it to your watchlist?',
                                                reply_markup=ReplyKeyboardMarkup(bool_keyboard,
                                                                                 one_time_keyboard=True,
                                                                                 resize_keyboard=True))
            return WATCHLIST_NO_TORR


@auth_wrap
def get_download_progress(update: Update, context: CallbackContext) -> int:
    user = update.effective_user['id']
    torrents = get_progress(user, logger=logger)
    for torrent in torrents[:5]:
        update.message.reply_text(f"{torrent['TorrentName']}\n"
                                  f"Resolution: {torrent['Resolution']}\n"
                                  f"Status: {torrent['Status']}\n"
                                  f"Progress: {torrent['Progress']}\n"
                                  f"ETA: {torrent['ETA']}")
    return break_level(update, context)


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
def break_level(update: Update, context: CallbackContext) -> None:
    """Dude u messed up :) """
    context.user_data.clear()
    update.message.reply_text(
        f"Ok, so, watcha wanna do next?",
        reply_markup=ReplyKeyboardMarkup(menu_keyboard, one_time_keyboard=True, resize_keyboard=True),
    )
    return CHOOSE_TASK


@auth_wrap
def change_watchlist_command(update: Update, context: CallbackContext) -> None:
    pkg = USERS[update.effective_user.id]
    if pkg['scan_watchlist'] == 0:
        pkg['scan_watchlist'] = 1
    else:
        pkg['scan_watchlist'] = 0
    update_many([pkg], User, User.telegram_chat_id)
    update.message.reply_text("Updated your watchlist preferences.")


@auth_wrap
def change_newsletter_command(update: Update, context: CallbackContext) -> None:
    pkg = USERS[update.effective_user.id]
    if pkg['email_newsletters'] == 0:
        pkg['email_newsletters'] = 1
    else:
        pkg['email_newsletters'] = 0
    update_many([pkg], User, User.telegram_chat_id)
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
    print('in rate title entry')
    context.user_data['pkg'] = {
        'imdb': int(update.message.text.replace('/RateTitle', '')),
    }

    message = f"Please choose a rating."
    update.effective_message.reply_html(message, reply_markup=ReplyKeyboardMarkup(rate_keyboard,
                                                                                  one_time_keyboard=True,
                                                                                  resize_keyboard=True,
                                                                                  ))
    return RATE_TITLE


@auth_wrap
def submit_rating(update: Update, context: CallbackContext) -> int:
    if update.message.text in [str(x) for x in list(range(1, 11))]:
        # Got rating
        item = get_my_movie_by_imdb(context.user_data['pkg']['imdb'], update.effective_user['id'])
        item['rating_status'] = 'rated in telegram'
        item['my_score'] = int(update.message.text)
        update_many([item], Movie, Movie.id)
        update.effective_message.reply_text(f"Ok, great! Here's a link if you also want to rate it on IMDB:\n"
                                            f"https://www.imdb.com/title/"
                                            f"{convert_imdb_id(context.user_data['pkg']['imdb'])}/")
        return break_level(update, context)

    elif update.message.text == "I've changed my mind":
        item = get_my_movie_by_imdb(context.user_data['pkg']['imdb'], update.effective_user['id'])
        item['rating_status'] = 'refused to rate'
        update_many([item], Movie, Movie.id)
        update.effective_message.reply_text("Ok, no worries! I won't bother you about this title anymore.\n"
                                            "Have a great day!")
        return break_level(update, context)
    else:
        update.effective_message.reply_text("Please choose an option from the keyboard.")
        return RATE_TITLE


@auth_wrap
def netflix_rate_or_not(update: Update, context: CallbackContext) -> int:
    if update.message.text == 'No':
        context.user_data['send_notifications'] = False
    else:
        context.user_data['send_notifications'] = True
    update.message.reply_text("K, now upload the .csv file please.")
    return NETFLIX_CSV


@auth_wrap
def netflix_csv(update: Update, context: CallbackContext) -> int:
    csv_context = {
        'user': update.effective_user.id,
        'file': update.message.document.file_id,
        'send_notifications': context.user_data['send_notifications'],
    }
    update.message.reply_text("Thanks!We started the upload process, we'll let you know "
                              "when it's done or if there's any trouble.")
    context.job_queue.run_once(
        callback=csv_upload_handler,
        context=csv_context,
        when=0
    )
    return break_level(update, context)


@auth_wrap
def netflix_no_csv(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("Upload the .csv or hit /reset to go back.")
    return NETFLIX_CSV


@auth_wrap
def netflix_no_rate_option(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("Choose Yes or No, bro.")
    return UPLOAD_ACTIVITY


@auth_wrap
def download_csv(update: Update, context: CallbackContext) -> int:
    csv_context = {
        'user': update.effective_user.id,
    }
    context.job_queue.run_once(
        callback=csv_download_handler,
        context=csv_context,
        when=0
    )
    return break_level(update, context)


def test(update, context, message):
    print('in test function')
    return ConversationHandler.END


@auth_wrap
def reset_command(update: Update, context: CallbackContext) -> None:
    context.user_data.clear()
    update.message.reply_text(
        text="BipBot reset. What's next?",
        reply_markup=ReplyKeyboardMarkup(menu_keyboard, one_time_keyboard=True, resize_keyboard=True),
    )
    return CHOOSE_TASK


def main() -> None:
    global USERS
    check_database()
    USERS = get_telegram_users()
    """Start the bot."""
    # Create the Updater and pass it your bot's token.
    updater = Updater(TELEGRAM_TOKEN)

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    choose_task_conversation_handler = ConversationHandler(
        entry_points=[
            CommandHandler('reset', reset_command),
            MessageHandler(Filters.regex(r'^/WatchMatch\d+$'), watchlist_entry),
            MessageHandler(Filters.regex(r'^/UnWatchMatch\d+$'), remove_watchlist_entry),
            MessageHandler(Filters.regex(r'^/RateTitle\d+$'), rate_title_entry),
            MessageHandler(Filters.text, choose_task)
        ],
        states={},
        fallbacks=[],
        map_to_parent={
            ConversationHandler.END: ConversationHandler.END,
            CHOOSE_TASK: CHOOSE_TASK,
            RATE_TITLE: RATE_TITLE,
            DOWNLOAD_MOVIE: DOWNLOAD_MOVIE,
            CHECK_PROGRESS: CHECK_PROGRESS,
            UPLOAD_ACTIVITY: UPLOAD_ACTIVITY,
            REGISTER_USER: REGISTER_USER,
        }
    )

    download_movie_conversation_handler = ConversationHandler(
        entry_points=[
            MessageHandler(
                Filters.regex('^([tT]{2})?\d+$'), parse_imdb_id
            ),
            MessageHandler(
                Filters.text, parse_imdb_text
            ),
        ],
        states={
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
            WATCHLIST_NO_TORR: [
                MessageHandler(
                    Filters.text, add_to_watchlist_no_torrent
                ),
            ],
        },
        fallbacks=[MessageHandler(Filters.command, test)],
        map_to_parent={
            ConversationHandler.END: ConversationHandler.END,
            DOWNLOAD_MOVIE: DOWNLOAD_MOVIE,
            CHOOSE_TASK: CHOOSE_TASK,
        }
    )

    check_progress_conversation_handler = ConversationHandler(
        entry_points=[
            MessageHandler(
                Filters.text, get_download_progress
            ),
            CallbackQueryHandler(
                get_download_progress
            )
        ],
        states={},
        fallbacks=[],
        map_to_parent={
            ConversationHandler.END: ConversationHandler.END,
            CHOOSE_TASK: CHOOSE_TASK,
            CHECK_PROGRESS: CHECK_PROGRESS,
        }
    )

    upload_activity_conversation_handler = ConversationHandler(
        entry_points=[
            CommandHandler('reset', reset_command),
            MessageHandler(
                Filters.regex("^Yes$|^No$"), netflix_rate_or_not
            ),
            MessageHandler(
                Filters.text, netflix_no_rate_option
            ),
        ],
        states={
            NETFLIX_CSV: [
                MessageHandler(
                    Filters.document, netflix_csv
                ),
                MessageHandler(
                    Filters.regex("^Yes$|^No$"), netflix_csv
                ),
                MessageHandler(
                    Filters.text, netflix_no_csv
                ),
            ],
        },
        fallbacks=[],
        map_to_parent={
            ConversationHandler.END: ConversationHandler.END,
            CHOOSE_TASK: CHOOSE_TASK,
            UPLOAD_ACTIVITY: UPLOAD_ACTIVITY,
        }
    )

    rate_title_conversation_handler = ConversationHandler(
        entry_points=[
            MessageHandler(
                Filters.text, submit_rating
            ),
        ],
        states={},
        fallbacks=[],
        map_to_parent={
            ConversationHandler.END: ConversationHandler.END,
            RATE_TITLE: RATE_TITLE,
            CHOOSE_TASK: CHOOSE_TASK,
        }
    )

    register_user_conversation_handler = ConversationHandler(
        entry_points=[
            CommandHandler('reset', reset_command),
            MessageHandler(
                Filters.text, check_riddle
            )
        ],
        states={
            CHECK_EMAIL: [
                CommandHandler('reset', reset_command),
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
                CommandHandler('reset', reset_command),
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
                    Filters.text, wrong_input_imdb
                ),
            ],
        },
        fallbacks=[],
        map_to_parent={
            ConversationHandler.END: ConversationHandler.END,
            REGISTER_USER: REGISTER_USER,
            CHOOSE_TASK: CHOOSE_TASK,
        }
    )

    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(Filters.regex(r'^/WatchMatch\d+$'), watchlist_entry),
            MessageHandler(Filters.regex(r'^/UnWatchMatch\d+$'), remove_watchlist_entry),
            MessageHandler(Filters.regex(r'^/RateTitle\d+$'), rate_title_entry),
            MessageHandler(Filters.text, start),
        ],
        states={
            CHOOSE_TASK: [choose_task_conversation_handler],
            DOWNLOAD_MOVIE: [download_movie_conversation_handler],
            CHECK_PROGRESS: [check_progress_conversation_handler],
            UPLOAD_ACTIVITY: [upload_activity_conversation_handler],
            RATE_TITLE: [rate_title_conversation_handler],
            REGISTER_USER: [register_user_conversation_handler],
        },
        fallbacks=[],
    )

    # dispatcher.add_handler(CommandHandler('reset', reset_command))
    dispatcher.add_handler(CommandHandler('help', help_command))
    dispatcher.add_handler(CommandHandler('change_watchlist', change_watchlist_command))
    dispatcher.add_handler(CommandHandler('change_newsletter', change_newsletter_command))
    dispatcher.add_handler(CommandHandler('update_user', update_user))
    dispatcher.add_handler(conv_handler)

    # Start the Bot
    updater.start_polling()
    job_queue = updater.job_queue
    job_queue.run_repeating(bot_watchlist_routine, interval=TELEGRAM_WATCHLIST_ROUTINE_INTERVAL * 60, first=5)
    job_queue.run_repeating(bot_rate_titles, interval=TELEGRAM_RATE_ROUTINE_INTERVAL * 60, first=5)

    updater.idle()


if __name__ == '__main__':
    main()
