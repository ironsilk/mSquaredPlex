import datetime
import logging
import os
import re
from functools import wraps
from random import randint

import sqlalchemy
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CallbackContext, CommandHandler, MessageHandler, filters, \
    ConversationHandler, CallbackQueryHandler
from transmission_rpc import TransmissionError

# removed: CSV feature import (feature deprecated)
# removed: progress feature import
from bot_utils import make_movie_reply, update_torr_db, \
    exclude_torrents_from_watchlist, get_movie_from_all_databases, search_imdb_title, add_to_watchlist, \
    get_telegram_users, invite_friend
from command_regex_handler import RegexpCommandHandler
from services.watchlist_service import get_torrents_for_imdb_id, update_watchlist_item_status
from utils import deconvert_imdb_id, send_torrent, compose_link, get_user_by_tgram_id, get_my_movie_by_imdb, \
    update_many, Movie, convert_imdb_id, check_database, User, get_onetimepasswords, remove_onetimepassword, \
    insert_onetimepasswords, get_movies_for_bulk_rating, make_client, update_torrent_status, update_torrent_grace_days, \
    get_torrent_by_torr_id_user

"""
IMPORTANT for SSL: add verify=False in
Anaconda3\envs\mSquaredPlex\Lib\site-packages\telegram\request\_httpxrequest.py
in self._client_kwargs = dict()
"""

# Enable logging
logging.basicConfig(
    format='[%(asctime)s] {%(filename)s:%(lineno)d} [%(name)s] [%(levelname)s] --> %(message)s', level=logging.DEBUG
)

logger = logging.getLogger('MovieTimeBot')

SUPERADMIN_PASSWORD = os.getenv('SUPERADMIN_PASSWORD')

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_AUTH_TEST_PATH = os.getenv('TELEGRAM_AUTH_TEST_PATH')
TELEGRAM_AUTH_APPROVE = os.getenv('TELEGRAM_AUTH_APPROVE')
TELEGRAM_IMDB_RATINGS = os.getenv('TELEGRAM_IMDB_RATINGS')
TELEGRAM_NETFLIX_PNG = os.getenv('TELEGRAM_NETFLIX_PNG')
TELEGRAM_RESET_PNG = os.getenv('TELEGRAM_RESET_PNG')

# State definitions for top level conversation
CHOOSE_TASK, REGISTER_USER, DOWNLOAD_MOVIE, CHECK_PROGRESS, UPLOAD_ACTIVITY, RATE_TITLE = range(6)

# State definitions  DOWNLOAD_MOVIE
CHOOSE_MULTIPLE, CHOOSE_ONE, CONFIRM_REDOWNLOAD_ACTION, SEARCH_FOR_TORRENTS, \
DOWNLOAD_TORRENT, WATCHLIST_NO_TORR = range(6, 12)

# State definitions for CHECK_PROGRESS
DOWNLOAD_PROGRESS = 12

# State definitions for UPLOAD_ACTIVITY
NETFLIX_CSV, UPLOAD_CSV = 13, 14

# State definitions for DOWNLOAD_ACTIVITY
DOWNLOAD_CSV = 15

# State definitions for RATE_TITLE
CHOOSE_WHAT_TO_RATE = 16
SUBMIT_RATING = 17

# State definitions for REGISTER_USER
CHECK_EMAIL, GIVE_IMDB, CHECK_IMDB = range(18, 21)

USERS = None

menu_keyboard = [
    ["📥 Download a movie"],
    ["🌡️ Rate a title"],
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
rate_keyboard_bulk = [
    ['1', '2'],
    ['3', '4'],
    ['5', '6'],
    ['7', '8'],
    ['9', '10'],
    ["Skip this movie."],
    ["Exit rating process."]
]


def auth_wrap(f):
    @wraps(f)
    async def wrap(update: Update, context: CallbackContext, *optional_args):
        # print(f"Wrapped {f.__name__}", )
        user = update.effective_user['id']
        if user in USERS.keys():
            # User is registered
            result = f(update, context, *optional_args)
            # print(result)
            return await result
        else:
            if USERS:
                # New user ask for password
                await update.message.reply_text("Please input the password provided by the admin")
                context.user_data['user_type'] = 'user'
            else:
                # No users registered, probably admin but check.
                await update.effective_message.reply_photo(
                    photo=open(TELEGRAM_AUTH_TEST_PATH, 'rb'),
                    caption="Looks like you're new here. Answer correctly and you may enter.",
                )
                context.user_data['user_type'] = 'admin'
            return REGISTER_USER

    return wrap


"""<< DOWNLOAD A MOVIE >>"""


@auth_wrap
async def start(update: Update, context: CallbackContext, message: str = '') -> int:
    """Send a message when the command /start is issued."""

    user = update.effective_user
    if not message:
        message = f"Hi {user.mention_markdown_v2()}\!\n" \
                  fr"Please select one of the options or type /help for more options\."
    await update.message.reply_markdown_v2(
        message,
        reply_markup=ReplyKeyboardMarkup(menu_keyboard, one_time_keyboard=True, resize_keyboard=True),
    )
    return CHOOSE_TASK


@auth_wrap
async def reset(update: Update, context: CallbackContext.DEFAULT_TYPE) -> int:
    """End Conversation by command."""

    await update.message.reply_text("See you next time. Type anything to get started.")

    return ConversationHandler.END


@auth_wrap
async def choose_task(update: Update, context: CallbackContext) -> int:
    """Choose between download a movie or rate a title"""
    txt = update.message.text
    logger.debug(f"choose_task received: {txt}")

    if txt == menu_keyboard[0][0]:
        message = 'Great, give me an IMDB id, a title or an IMDB link.'
        context.user_data['action'] = 'download'
        await update.message.reply_text(message)
        return DOWNLOAD_MOVIE

    elif txt == menu_keyboard[1][0]:
        await update.effective_message.reply_text('Do you wish to rate a new title or a seen but unrated movie?',
                                                  reply_markup=ReplyKeyboardMarkup([['New title', 'Rate seen movies']],
                                                                                   one_time_keyboard=True,
                                                                                   resize_keyboard=True,
                                                                                   ))
        return RATE_TITLE

    message = 'Please choose one of the options\.'
    return await start(update, context, message)


@auth_wrap
async def parse_imdb_id(update: Update, context: CallbackContext) -> int:
    """Get data about movie, using the IMDB id.
        Queries the internal database and calls the APIs if necessary."""

    await update.message.reply_text("Just a sec until we get data about this title...")
    # We need number so filter out the number from the user input:
    imdb_id = ''.join([x for x in update.message.text if x.isdigit()]).lstrip('0')

    # Get IMDB data
    pkg = get_movie_from_all_databases(imdb_id, update.effective_user['id'])
    context.user_data['pkg'] = pkg
    context.user_data['more_options'] = False

    message, image = make_movie_reply(pkg)
    await update.effective_message.reply_photo(
        photo=image,
        caption=message,
        reply_markup=ReplyKeyboardMarkup(movie_selection_keyboard,
                                         one_time_keyboard=True,
                                         resize_keyboard=True,
                                         ),
    )
    return CHOOSE_ONE


@auth_wrap
async def parse_imdb_text(update: Update, context: CallbackContext) -> int:
    """Route the query if the string is a link or a title."""

    q = update.message.text
    logger.debug(f"parse_imdb_text query: {q}")
    await update.message.reply_text("Just a sec until we get data about this title...")
    # Is it a link?
    try:
        imdb_id = re.search(r"[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)",
                            q).group(0)
        logger.debug(f"Detected link: {imdb_id}")

        # We need number so filter out the number from the user input:
        imdb_id = ''.join([x for x in imdb_id if x.isdigit()]).lstrip('0')

        # Get IMDB data
        pkg = get_movie_from_all_databases(imdb_id, update.effective_user['id'])
        context.user_data['pkg'] = pkg
        logger.debug(f"Link-resolved imdb_id={imdb_id}, pkg_imdb={pkg.get('imdb') if pkg else None}")

        message, image = make_movie_reply(pkg)
        await update.effective_message.reply_photo(
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
        if 'https://' in q:
            await update.effective_message.reply_text("Couldn't find the specified ID in the link, are you"
                                                      "sure it's an IMDB link? Try pasting only the ID, as in"
                                                      "`tt0903624`.")
            return DOWNLOAD_MOVIE
        else:
            # Title search
            movies = search_imdb_title(q)
            logger.debug(f"Title search results: {len(movies) if isinstance(movies, list) else movies}")
            context.user_data['potential_titles'] = movies
            return await choose_multiple(update, context)


@auth_wrap
async def choose_multiple(update: Update, context: CallbackContext) -> int:
    """Loop through potential movie matches"""

    movies = context.user_data['potential_titles']
    logger.debug(f"choose_multiple: remaining candidates={len(movies) if isinstance(movies, list) else 'invalid'}")
    if movies:
        if isinstance(movies, str):
            await update.effective_message.reply_text("We're having trouble with our IMDB API, please"
                                                      "insert an IMDB ID or paste a link.")
            return DOWNLOAD_MOVIE
        movie = movies.pop(0)
        logger.debug(f"Trying candidate imdb_id={movie.get('id')} title={movie.get('title')} year={movie.get('year')}")
        # Check again if we can find it
        pkg = get_movie_from_all_databases(movie['id'], update.effective_user['id'])
        if pkg:
            context.user_data['pkg'] = pkg
            logger.debug(f"Candidate resolved to pkg_imdb={pkg.get('imdb')}")
            message, image = make_movie_reply(pkg)
            await update.effective_message.reply_photo(
                photo=image,
                caption=message,
                reply_markup=ReplyKeyboardMarkup(movie_selection_keyboard,
                                                 one_time_keyboard=True,
                                                 resize_keyboard=True,
                                                 ),
            )
            return CHOOSE_ONE
        else:
            logger.debug("Candidate not found in DB/APIs, trying next")
            return await choose_multiple(update, context)
    else:
        await update.effective_message.reply_text("Couldn't find the specified movie."
                                                  " Check your spelling or try pasting the IMDB id or a link"
                                                  "`tt0903624`.")
        return DOWNLOAD_MOVIE


@auth_wrap
async def accept_reject_title(update: Update, context: CallbackContext) -> int:
    """Accept, reject the match or exit"""
    choice = update.message.text
    logger.debug(f"accept_reject_title: user chose '{choice}' for imdb={context.user_data.get('pkg', {}).get('imdb')}")
    if choice == 'Yes':
        if context.user_data['action'] == 'download':
            return await check_movie_status(update, context)
        else:
            return await rating_movie_info(update, context)
    elif choice == 'No':
        if context.user_data['potential_titles']:
            await update.effective_message.reply_text("Ok, trying next hit...")
            return await choose_multiple(update, context)
        else:
            await update.effective_message.reply_text("These were all the hits. Sorry. Feel free to type anything "
                                                      "to start again")
            return await reset(update, context)
    elif choice == 'Exit':
        return await reset(update, context)
    else:
        await update.effective_message.reply_text("Please choose one of the options.")


@auth_wrap
async def check_movie_status(update: Update, context: CallbackContext) -> int:
    """Customise the message depending on the status of the movie
        (seen, already downloaded)"""

    movie = context.user_data['pkg']
    # Check if you've already seen it and send info
    if movie['already_in_my_movies']:
        message = f"Looks like you've already seen this movie."
        if 'my_score' in movie.keys():
            message += f"\nYour score: {movie['my_score']}"
        if 'seen_date' in movie.keys():
            message += f"\nAnd you've seen it on {movie['seen_date']}"
        await update.message.reply_text(message)
        if movie['torr_result']:
            message = f"Looks like the movie is also downloaded in {movie['resolution']}p\n" \
                      f"Torrent status: {movie['torr_status']}\n" \
                      f"Would you still like to proceed to download?"
        else:
            message = f"\nWould you still like to proceed to download?"

        await update.effective_message.reply_html(message, reply_markup=ReplyKeyboardMarkup(bool_keyboard,
                                                                                            one_time_keyboard=True,
                                                                                            resize_keyboard=True,
                                                                                            ))
        return CONFIRM_REDOWNLOAD_ACTION
    else:
        return await search_for_torrents(update, context)


@auth_wrap
async def search_for_torrents(update: Update, context: CallbackContext) -> int:
    """Search for torrents for the given IMDB id
        Build keyboard to show them"""

    imdb_num = context.user_data['pkg']['imdb']
    logger.debug(f"search_for_torrents: querying torrents for imdb={imdb_num}")
    await update.message.reply_text('Searching for available torrents...')
    torrents = get_torrents_for_imdb_id(imdb_num)
    logger.debug(f"search_for_torrents: fetched {len(torrents) if torrents else 0} candidates from API")
    torrents = sorted(torrents, key=lambda k: k.get('size', 0))
    if torrents:
        context.user_data['pkg']['torrents'] = torrents
        keyboard = [[]]
        for pos, item in enumerate(torrents, start=1):
            size_gb = round((item.get('size', 0) or 0) / 1000000000, 2)
            btn_text = (
                f"🖥 Q: {str(item.get('resolution'))} "
                f"🗳 S: {size_gb} GB "
                f"🌱 S/P: {str(item.get('seeders'))}/{str(item.get('leechers'))}"
            )
            btn = InlineKeyboardButton(btn_text, callback_data=str(item.get('id')))
            keyboard.append([btn])
        # Add button for None
        keyboard.append([InlineKeyboardButton('None, thanks', callback_data='0')])
        await update.message.reply_text(
            f"Please select one of the torrents",
            reply_markup=InlineKeyboardMarkup(keyboard, one_time_keyboard=True),
        )
        return DOWNLOAD_TORRENT
    else:
        await update.message.reply_text(
            "We couldn't find any torrents for this title.\n"
            "Would you like to add it to your watchlist?",
            reply_markup=ReplyKeyboardMarkup(bool_keyboard, one_time_keyboard=True, resize_keyboard=True),
        )
        return WATCHLIST_NO_TORR


@auth_wrap
async def confirm_redownload_action(update: Update, context: CallbackContext) -> int:
    """Ask user if he really wants to download the movie given that
        he's aready seen it or it's already in transmission"""

    if update.message.text == 'Yes':
        if context.user_data['action'] == 'download':
            return await search_for_torrents(update, context)
        else:
            return await rate_title(update, context)
    else:
        return await reset(update, context)


@auth_wrap
async def download_torrent(update: Update, context: CallbackContext) -> int:
    """Send download request to transmission"""

    query = update.callback_query
    await query.answer()
    if query.data != '0':
        await query.edit_message_text(text=f"Thanks, sending download request...")
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
        await query.edit_message_text(text=message)
        if 'from_watchlist' in context.user_data.keys():
            return ConversationHandler.END
        return CHOOSE_TASK
    else:
        if 'from_watchlist' in context.user_data.keys():
            await query.edit_message_text(text="Ok, i'll remove these torrent options from future watchlist alerts "
                                               "regarding this movie.")
            return await exclude_res_from_watchlist(update, context)
        else:
            await update.effective_message.reply_text('Would you like to add it to your watchlist?',
                                                      reply_markup=ReplyKeyboardMarkup(bool_keyboard,
                                                                                       one_time_keyboard=True,
                                                                                       resize_keyboard=True))
            return WATCHLIST_NO_TORR


@auth_wrap
async def exclude_res_from_watchlist(update: Update, context: CallbackContext) -> int:
    """Function gets called only when a watchlist allert appears.
        If the user refuses to download, the current movie resolution will be
        excluded from further alerts."""

    torrents = context.user_data['pkg']['torrents']
    movie_id = deconvert_imdb_id(torrents[0]['imdb'])
    exclude_torrents_from_watchlist(movie_id, update.effective_user['id'], [x['id'] for x in torrents])
    await update.callback_query.edit_message_text(text="Removed these torrent quality for future recommendations "
                                                       "on this title. Type anything to get started")
    return ConversationHandler.END


@auth_wrap
async def add_to_watchlist_no_torrent(update: Update, context: CallbackContext) -> int:
    """Add movie to watchlist if no torrent is currently available.
        If torrents for the movie ARE available but the user still wants to add to
        watchlist, the movie is added but user will be notified only when another
        resolution for the movie becomes available."""

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
        await update.message.reply_text(message)

    return await reset(update, context)


"""<< CHECK DOWNLOAD PROGRESS >>"""


# Removed: get_download_progress feature deprecated


"""<< UPLOAD ACTIVITY >>"""


@auth_wrap
async def netflix_rate_or_not(update: Update, context: CallbackContext) -> int:
    """Deprecated: CSV import has been removed."""
    await update.message.reply_text("CSV import has been removed.")
    return NETFLIX_CSV


@auth_wrap
async def netflix_csv(update: Update, context: CallbackContext) -> int:
    """Deprecated: CSV import has been removed."""
    await update.message.reply_text("CSV import has been removed.")
    return NETFLIX_CSV


@auth_wrap
async def netflix_no_csv(update: Update, context: CallbackContext) -> int:
    """Deprecated: CSV import has been removed."""
    await update.message.reply_text("CSV import has been removed.")
    return NETFLIX_CSV


"""<< RATE A TITLE >>"""


@auth_wrap
async def choose_what_to_rate(update: Update, context: CallbackContext) -> int:
    if update.message.text == 'New title':
        message = 'Great, give me an IMDB id, a title or an IMDB link.'
        context.user_data['action'] = 'rate'
        await update.message.reply_text(message)
        return DOWNLOAD_MOVIE

    elif update.message.text == 'Rate seen movies':
        await update.message.reply_text("Preparing movies...")
        context.user_data['unrated_movies'] = get_movies_for_bulk_rating(update.effective_user['id'])
        if context.user_data['unrated_movies']:
            return await rate_multiple(update, context)
        else:
            await update.message.reply_text("You have no unrated movies!")
            return await start(update, context, "Can i help you with anything else?")


@auth_wrap
async def rate_multiple(update: Update, context: CallbackContext) -> int:
    movies = context.user_data['unrated_movies']
    if movies:
        movie = movies.pop(0)
        # Check again if we can find it
        pkg = get_movie_from_all_databases(movie['imdb_id'], update.effective_user['id'])
        if pkg:
            context.user_data['pkg'] = pkg
            message, image = make_movie_reply(pkg)
            message += "\nPlease choose a rating"
            await update.effective_message.reply_photo(
                photo=image,
                caption=message,
                reply_markup=ReplyKeyboardMarkup(rate_keyboard_bulk,
                                                 one_time_keyboard=True,
                                                 resize_keyboard=True,
                                                 ),
            )
            context.user_data['rate_origin'] = 'multiple'
            return SUBMIT_RATING
        else:
            return await rate_multiple(update, context)
    else:
        await update.effective_message.reply_text("No more movies left, good job!")
        return await start(update, context, "Can i help you with anything else?")


@auth_wrap
async def rating_movie_info(update: Update, context: CallbackContext) -> int:
    movie = context.user_data['pkg']
    # Check if you've already seen it and send info
    if movie['already_in_my_movies']:
        message = f"Movie seen"
        if 'seen_date' in movie.keys():
            message = message + f" on {movie['seen_date']}"
        if 'my_score' in movie.keys():
            message += f"\nYour score: {movie['my_score']}"
        await update.message.reply_text(message)
        message = f"\nWould you like to rate it again?"
        await update.effective_message.reply_html(message, reply_markup=ReplyKeyboardMarkup(bool_keyboard,
                                                                                            one_time_keyboard=True,
                                                                                            resize_keyboard=True,
                                                                                            ))
        return CONFIRM_REDOWNLOAD_ACTION
    else:
        return await rate_title(update, context)


@auth_wrap
async def rate_title(update: Update, context: CallbackContext) -> int:
    context.user_data['rate_origin'] = 'simple'
    message = f"Great, please choose a rating:"
    await update.effective_message.reply_html(message, reply_markup=ReplyKeyboardMarkup(rate_keyboard,
                                                                                        one_time_keyboard=True,
                                                                                        resize_keyboard=True,
                                                                                        ))
    return SUBMIT_RATING


@auth_wrap
async def rate_title_plex_triggered(update: Update, context: CallbackContext, passed_args) -> int:
    context.user_data['pkg'] = {
        'imdb': int(passed_args)
    }
    return await rate_title(update, context)


@auth_wrap
async def submit_rating(update: Update, context: CallbackContext) -> int:
    """User receives a message from an external routine
        If he clicks on it this function gets triggered."""
    if context.user_data['rate_origin'] == 'simple':
        return1_func = reset
        message1 = "Ok, no worries! I won't bother you about this title anymore.\n" \
                   "Have a great day!"
        return2_func = reset
    else:
        return1_func = rate_multiple
        message1 = "Ok, no worries! I won't bother you about this title anymore.\n"
        return2_func = rate_multiple

    if update.message.text in [str(x) for x in list(range(1, 11))]:
        # Got rating
        item = get_my_movie_by_imdb(context.user_data['pkg']['imdb'], update.effective_user['id'])
        if item:
            item['rating_status'] = 'rated in telegram'
            item['my_score'] = int(update.message.text)
            item['seen_date'] = datetime.datetime.now()
        else:
            item = {
                'imdb_id': context.user_data['pkg']['imdb'],
                'my_score': int(update.message.text),
                'rating_status': 'rated in telegram',
                'user_id': update.effective_user['id'],
                'seen_date': datetime.datetime.now(),
            }
        update_many([item], Movie, Movie.id)
        await update.effective_message.reply_text(f"Ok, great! Here's a link if you also want to rate it on IMDB:\n"
                                                  f"https://www.imdb.com/title/"
                                                  f"{convert_imdb_id(context.user_data['pkg']['imdb'])}/",
                                                  disable_web_page_preview=True)
        return await return1_func(update, context)

    elif update.message.text in [rate_keyboard[-1][0], rate_keyboard_bulk[-2][0]]:
        item = get_my_movie_by_imdb(context.user_data['pkg']['imdb'], update.effective_user['id'])
        if item:
            item['rating_status'] = 'refused to rate'
        else:
            item = {
                'imdb_id': context.user_data['pkg']['imdb'],
                'rating_status': 'refused to rate',
                'user_id': update.effective_user['id'],
            }
        update_many([item], Movie, Movie.id)
        await update.effective_message.reply_text(message1)
        return await return2_func(update, context)
    elif update.message.text == rate_keyboard_bulk[-1][0]:
        await update.effective_message.reply_text("Ok, your progress is saved, come back anytime.")
        return await start(update, context)
    else:
        await update.effective_message.reply_text("Please choose an option from the keyboard.")
        return SUBMIT_RATING


"""<< AUTHENTICATION >>"""


async def check_user(update: Update, context: CallbackContext):
    if context.user_data['user_type'] == 'user':
        onetime_passwords = get_onetimepasswords()
        passwords = [x['password'] for x in onetime_passwords]
        expiry_dates = [x['expiry'] for x in onetime_passwords]
        user_types = [x['user_type'] for x in onetime_passwords]
        try:
            pwd = int(update.message.text)
            if pwd in passwords and datetime.datetime.now() < expiry_dates[passwords.index(pwd)]:
                remove_onetimepassword(pwd)
                context.user_data['user_type'] = user_types[passwords.index(pwd)]
                return await password_ok(update, context)
            else:
                await update.effective_message.reply_text("Password expired, please contact "
                                                          "the admin and try again.")
                return REGISTER_USER
        except ValueError:
            pass
    else:
        if update.message.text.lower() == SUPERADMIN_PASSWORD:
            return await password_ok(update, context)
    await update.effective_message.reply_text("Incorrect password")
    return REGISTER_USER


async def password_ok(update: Update, context: CallbackContext):
    await update.effective_message.reply_photo(
        photo=open(TELEGRAM_AUTH_APPROVE, 'rb'),
        caption="Welcome! Just a few more steps to configure your preferences. "
                "First, please type in your email so that we can add you "
                "to our PLEX users.",
    )
    return CHECK_EMAIL


async def check_email(update: Update, context: CallbackContext):
    # Invite to PLEX server
    email_invite = invite_friend(update.message.text)
    if email_invite:
        message = "Great! An invitation for PLEX has been sent to your email.\n"
    else:
        message = "Looks like either this email is already in our PLEX users database " \
                  "OR you're not planning to use PLEX.\n" \
                  "If this is not the case, please contact the admin.\n\n"

    # Continue to IMDB stuff
    context.user_data['new_user'] = {
        'telegram_chat_id': update.message.chat_id,
        'telegram_name': update.effective_user.first_name,
        'email': update.message.text,
        'email_newsletters': True,
        'scan_watchlist': False,
        'user_type': context.user_data['user_type']

    }
    message += "Would you like to connect your IMDB account? " \
               "In this way we'll be able to pull your movie " \
               "ratings and warn you when you'll search for a movie " \
               "you've already seen.\n" \
               "We'll also scan your watchlist periodically and notify you " \
               "when we'll be able to download any of the titles there.\n" \
               "In the future we're planning to be able to " \
               "give ratings here and transfer them to IMDB."
    await update.effective_message.reply_text(message, reply_markup=ReplyKeyboardMarkup(bool_keyboard,
                                                                                        one_time_keyboard=True,
                                                                                        resize_keyboard=True,
                                                                                        ))
    return GIVE_IMDB


async def give_imdb(update: Update, context: CallbackContext):
    if update.message.text == 'Yes':
        await update.effective_message.reply_photo(
            photo=open(TELEGRAM_IMDB_RATINGS, 'rb'),
            caption="I'll need you to go to your IMDB account and copy here your user ID, like the one in the photo, "
                    "ur77571297. Also make sure that your Ratings are PUBLIC and so is your Watchlist (10 pages max).\n"
                    "If this is too much, just type 'fuck it' and skip this step.\n"
                    "https://www.imdb.com/",
        )
        return CHECK_IMDB
    else:
        return await register_user(update, context)


async def check_imdb(update: Update, context: CallbackContext):
    if update.message.text.lower() != 'fuck it':
        context.user_data['new_user']['scan_watchlist'] = True
        context.user_data['new_user']['imdb_id'] = ''.join([x for x in update.message.text if x.isdigit()])
    return await register_user(update, context)


async def register_user(update: Update, context: CallbackContext):
    global USERS
    # Update user to database
    update_many([context.user_data['new_user']], User, User.telegram_chat_id)
    USERS = get_telegram_users()
    message = "Ok, that's it\. I'll take care of the rest, from now on " \
              "anytime you type something i'll be here to help you out\. Enjoy\!\n" \
              "Type /help to find out more\."
    return await start(update, context, message)


def wrong_input(update: Update, context: CallbackContext):
    update.effective_message.reply_text("Wrong input, please try again.")
    return CHECK_EMAIL


def wrong_input_imdb(update: Update, context: CallbackContext):
    update.effective_message.reply_text("Wrong input, please try again.")
    return CHECK_IMDB


"""<< DOWNLOAD MOVIE DATABASE (CSV) >>"""


@auth_wrap
async def download_csv(update: Update, context: CallbackContext) -> None:
    """Deprecated: CSV export has been removed."""
    await update.message.reply_text("CSV import/export has been removed.")
    return None


"""<< OTHER FUNCTIONS >>"""


@auth_wrap
async def help_command(update: Update, context: CallbackContext) -> None:
    """Displays info on how to use the bot."""

    watchlist_status = 'MONITORING' if USERS[update.effective_user.id]['scan_watchlist'] == 1 else 'NOT MONITORING'
    email_status = 'RECEIVING' if USERS[update.effective_user.id]['email_newsletters'] else 'NOT RECEIVING'
    generate_password = '\n\nGENERATE CODE FOR NEW USER: run command /generate_pass. If you want the user to have ' \
                        'admin privileges, use -admin flag (/generate_pass -admin)' if \
        USERS[update.effective_user.id]['user_type'] == 'admin' else ' '
    await update.message.reply_text("Type anything for the bot to start.\n\n"
                                    "If i lose my shit just type /reset anytime.\n\n"
                                    f"Right now we are {watchlist_status} your watchlist. "
                                    f"Type /change_watchlist "
                                    "to reverse the status.\n\n"
                                    f"Right now you are {email_status} the email newsletters. Type /change_newsletter "
                                    "to reverse the status.\n\n"
                                    "If you want to change your email address or your imdb ID type /update_user "
                                    "and we'll ask you to retake the login process. Once started, you must complete "
                                    "the entire process."
                                    f"{generate_password}")
    # don't change state
    return None


@auth_wrap
async def generate_password(update: Update, context: CallbackContext) -> None:
    def insert_pwd(pwd):
        try:
            insert_onetimepasswords(pwd)
        except sqlalchemy.exc.IntegrityError:
            pwd['password'] = randint(10000, 99999)
            insert_pwd(pwd)
        return pwd['password']

    if not USERS[update.effective_user.id]['user_type'] == 'admin':
        return None
    else:
        arguments = (' '.join(context.args)).strip()
        pwd = {
            'password': randint(10000, 99999),
            'expiry': datetime.datetime.now() + datetime.timedelta(days=1)
        }
        if arguments == '-admin':
            pwd['user_type'] = 'admin'
        else:
            pwd['user_type'] = 'user'
        pwd = insert_pwd(pwd)
        await update.message.reply_text(f"Token {pwd} available for 24 hours")
        return None


@auth_wrap
async def update_user(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text('Type anything to get started.')
    del USERS[update.effective_user.id]


@auth_wrap
async def watchlist_entry(update: Update, context: CallbackContext, *passed_args) -> int:
    context.user_data['pkg'] = {
        'imdb': int(passed_args[0]),
    }
    context.user_data['from_watchlist'] = True
    await update.message.reply_text('Watchlist entry')
    return await search_for_torrents(update, context)


@auth_wrap
async def remove_watchlist_entry(update: Update, context: CallbackContext, *passed_args) -> int:
    movie_id = int(passed_args[0])
    update_watchlist_item_status(movie_id, update.effective_user['id'], 'closed')
    await update.message.reply_text("Done, no more watchlist updates for this movie.")
    return ConversationHandler.END


@auth_wrap
async def keep_torrent(update: Update, context: CallbackContext, *passed_args) -> int:
    torr_id = int(passed_args[0])
    update_torrent_grace_days(torr_id, update.effective_user['id'])
    await update.message.reply_text("Ok, done.")
    return ConversationHandler.END


@auth_wrap
async def remove_torrent(update: Update, context: CallbackContext, *passed_args) -> int:
    db_torr_id = int(passed_args[0])
    # remove torrent and data
    client = make_client()
    torrents = client.get_torrents()
    db_torr = get_torrent_by_torr_id_user(db_torr_id, update.effective_user['id'])
    try:
        torrent = [x for x in torrents if x.hashString == db_torr['torr_hash']][0]
    except IndexError:
        await update.message.reply_text("Error while removing torrent,\n"
                                        "please contact admin:).")
        return ConversationHandler.END
    client.remove_torrent(torrent.id, delete_data=True)
    # change status
    update_torrent_status(db_torr_id, 'removed')
    await update.message.reply_text("Torrent and files removed.")
    return ConversationHandler.END


@auth_wrap
async def seed_forever_torrent(update: Update, context: CallbackContext, *passed_args) -> int:
    torr_id = int(passed_args[0])
    update_torrent_grace_days(torr_id, update.effective_user['id'], 99999)
    await update.message.reply_text("Done, SeedMaster.")
    return ConversationHandler.END


@auth_wrap
async def change_watchlist_command(update: Update, context: CallbackContext) -> None:
    pkg = USERS[update.effective_user.id]
    pkg['telegram_chat_id'] = update.effective_user.id
    if pkg['scan_watchlist'] == 0:
        pkg['scan_watchlist'] = 1
    else:
        pkg['scan_watchlist'] = 0
    update_many([pkg], User, User.telegram_chat_id)
    await update.message.reply_text("Updated your watchlist preferences.")


@auth_wrap
async def change_newsletter_command(update: Update, context: CallbackContext) -> None:
    pkg = USERS[update.effective_user.id]
    pkg['telegram_chat_id'] = update.effective_user.id
    if pkg['email_newsletters'] == 0:
        pkg['email_newsletters'] = 1
    else:
        pkg['email_newsletters'] = 0
    update_many([pkg], User, User.telegram_chat_id)
    await update.message.reply_text("Updated your newsletter preferences.")


def main() -> None:
    """
    Main function, runs bot and all other services
    """

    global USERS
    check_database()
    USERS = get_telegram_users()

    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    download_movie_conversation_handler = ConversationHandler(
        entry_points=[
            RegexpCommandHandler(r'WatchMatch_[\d]+', watchlist_entry),
            MessageHandler(filters.Regex('^([tT]{2})?\d+$') & (~filters.COMMAND), parse_imdb_id),
            MessageHandler(filters.TEXT & (~filters.COMMAND), parse_imdb_text),
        ],
        states={
            CHOOSE_MULTIPLE: [
                MessageHandler(filters.TEXT & (~filters.COMMAND), choose_multiple)],
            CHOOSE_ONE: [
                MessageHandler(filters.TEXT & (~filters.COMMAND), accept_reject_title)],
            CONFIRM_REDOWNLOAD_ACTION: [
                MessageHandler(filters.TEXT & (~filters.COMMAND), confirm_redownload_action)],
            SEARCH_FOR_TORRENTS: [
                MessageHandler(filters.TEXT & (~filters.COMMAND), search_for_torrents)],
            DOWNLOAD_TORRENT: [
                CallbackQueryHandler(download_torrent)],
            WATCHLIST_NO_TORR: [
                MessageHandler(filters.TEXT & (~filters.COMMAND), add_to_watchlist_no_torrent), ],
        },
        fallbacks=[CommandHandler("reset", reset)],
        map_to_parent={
            CHOOSE_TASK: CHOOSE_TASK,
            DOWNLOAD_MOVIE: DOWNLOAD_MOVIE,
            SUBMIT_RATING: SUBMIT_RATING,
            ConversationHandler.END: ConversationHandler.END
        }
    )

    # Removed: check_download_progress conversation handler deprecated

    rate_title_conversation_handler = ConversationHandler(
        entry_points=[
            RegexpCommandHandler(r'RateTitle_[\d]+', rate_title_plex_triggered),
            MessageHandler(filters.TEXT & (~filters.COMMAND), choose_what_to_rate), ],
        states={
            DOWNLOAD_MOVIE: [
                download_movie_conversation_handler
            ],
            SUBMIT_RATING: [
                MessageHandler(filters.TEXT & (~filters.COMMAND), submit_rating, )],
        },
        fallbacks=[],
        map_to_parent={
            CHOOSE_TASK: CHOOSE_TASK,
            RATE_TITLE: RATE_TITLE,
            ConversationHandler.END: ConversationHandler.END
        }
    )

    register_user_conversation_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.TEXT & (~filters.COMMAND), check_user)],
        states={
            CHECK_EMAIL: [
                MessageHandler(filters.Regex('[^@]+@[^@]+\.[^@]+') & (~filters.COMMAND), check_email),
                MessageHandler(filters.TEXT & (~filters.COMMAND), wrong_input, )],
            GIVE_IMDB: [
                MessageHandler(filters.TEXT & (~filters.COMMAND), give_imdb, )],
            CHECK_IMDB: [
                MessageHandler(filters.Regex('^[u]?[r]?\d+$') & (~filters.COMMAND), check_imdb),
                MessageHandler(filters.TEXT & (~filters.COMMAND), wrong_input_imdb),
            ],
        },
        fallbacks=[CommandHandler('reset', reset)],
        map_to_parent={
            REGISTER_USER: REGISTER_USER,
            CHOOSE_TASK: CHOOSE_TASK,
            ConversationHandler.END: ConversationHandler.END
        }
    )

    conversation_handler = ConversationHandler(
        entry_points=[
            RegexpCommandHandler(r'WatchMatch_[\d]+', watchlist_entry),
            RegexpCommandHandler(r'RateTitle_[\d]+', rate_title_plex_triggered),
            MessageHandler(filters.TEXT & (~filters.COMMAND), start),
        ],
        states={
            CHOOSE_TASK: [MessageHandler(filters.TEXT & (~filters.COMMAND), choose_task)],
            DOWNLOAD_MOVIE: [download_movie_conversation_handler],
            RATE_TITLE: [rate_title_conversation_handler],
            REGISTER_USER: [register_user_conversation_handler],
            DOWNLOAD_TORRENT: [CallbackQueryHandler(download_torrent)],
            SUBMIT_RATING: [MessageHandler(filters.TEXT & (~filters.COMMAND), submit_rating)],
        },
        fallbacks=[
            CommandHandler("reset", reset),
            CommandHandler('help', help_command),
            CommandHandler('generate_pass', generate_password),
            CommandHandler('update_user', update_user),
            CommandHandler('change_watchlist', change_watchlist_command),
            CommandHandler('change_newsletter', change_newsletter_command),
            (RegexpCommandHandler(r'RateTitle_[\d]+', rate_title_plex_triggered)),
            (RegexpCommandHandler(r'WatchMatch_[\d]+', watchlist_entry)),
            (RegexpCommandHandler(r'UnWatchMatch_[\d]+', remove_watchlist_entry)),
            (RegexpCommandHandler(r'Keep_[\d]+', keep_torrent)),
            (RegexpCommandHandler(r'Remove_[\d]+', remove_torrent)),
            (RegexpCommandHandler(r'SeedForever_[\d]+', seed_forever_torrent)),

        ]
    )

    application.add_handler(conversation_handler)
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('generate_pass', generate_password))
    application.add_handler(CommandHandler('update_user', update_user))
    application.add_handler(RegexpCommandHandler(r'RateTitle_[\d]+', rate_title_plex_triggered))
    application.add_handler(RegexpCommandHandler(r'WatchMatch_[\d]+', watchlist_entry))
    application.add_handler(RegexpCommandHandler(r'UnWatchMatch_[\d]+', remove_watchlist_entry))
    application.add_handler(RegexpCommandHandler(r'Keep_[\d]+', keep_torrent))
    application.add_handler(RegexpCommandHandler(r'Remove_[\d]+', remove_torrent))
    application.add_handler(RegexpCommandHandler(r'SeedForever_[\d]+', seed_forever_torrent))
    application.add_handler(CommandHandler('change_watchlist', change_watchlist_command))
    application.add_handler(CommandHandler('change_newsletter', change_newsletter_command))
    application.run_polling(stop_signals=None)


if __name__ == '__main__':
    main()
