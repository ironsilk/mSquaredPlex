import logging
import os
import re
from functools import wraps

from telegram import InlineQueryResultArticle, InputTextMessageContent
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CallbackContext, CommandHandler, MessageHandler, filters, \
    ConversationHandler, CallbackQueryHandler
from transmission_rpc import TransmissionError
from bot_get_progress import get_progress
from bot_utils import make_movie_reply, update_torr_db, \
    exclude_torrents_from_watchlist, get_movie_from_all_databases, search_imdb_title, add_to_watchlist
from bot_watchlist import get_torrents_for_imdb_id
from bot_csv import csv_upload_handler, csv_download_handler
from utils import deconvert_imdb_id, send_torrent, compose_link, get_user_by_tgram_id

"""
IMPORTANT for SSL: add verify=False in
Anaconda3\envs\mSquaredPlex\Lib\site-packages\telegram\request\_httpxrequest.py
in self._client_kwargs = dict()
"""

# Enable logging
logging.basicConfig(
    format='[%(asctime)s] {%(filename)s:%(lineno)d} [%(name)s] [%(levelname)s] --> %(message)s', level=logging.INFO
)

logger = logging.getLogger('MovieTimeBot')

USE_PLEX = bool(os.getenv('USE_PLEX'))
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_AUTH_TEST_PATH = os.getenv('TELEGRAM_AUTH_TEST_PATH')
TELEGRAM_AUTH_APPROVE = os.getenv('TELEGRAM_AUTH_APPROVE')
TELEGRAM_IMDB_RATINGS = os.getenv('TELEGRAM_IMDB_RATINGS')
TELEGRAM_NETFLIX_PNG = os.getenv('TELEGRAM_NETFLIX_PNG')
TELEGRAM_RESET_PNG = os.getenv('TELEGRAM_RESET_PNG')
TELEGRAM_WATCHLIST_ROUTINE_INTERVAL = int(os.getenv('TELEGRAM_WATCHLIST_ROUTINE_INTERVAL'))
TELEGRAM_RATE_ROUTINE_INTERVAL = int(os.getenv('TELEGRAM_RATE_ROUTINE_INTERVAL'))

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
SUBMIT_RATING = 16

# State definitions for REGISTER_USER
CHECK_EMAIL, GIVE_IMDB, CHECK_IMDB = range(17, 20)

# State definitions for aux functions
RESET_CONVERSATION = 21

USERS = {
    1700079840: None
}

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


def auth_wrap(f):
    @wraps(f)
    def wrap(update: Update, context: CallbackContext):
        print(f"Wrapped {f.__name__}", )
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
            return echo

    return wrap


"""<< DOWNLOAD A MOVIE >>"""


@auth_wrap
async def start(update: Update, context: CallbackContext) -> int:
    """Send a message when the command /start is issued."""

    user = update.effective_user
    await update.message.reply_markdown_v2(
        f"Hi {user.mention_markdown_v2()}\!\n"
        fr"Please select one of the options or type /help for more options\.",
        reply_markup=ReplyKeyboardMarkup(menu_keyboard, one_time_keyboard=True, resize_keyboard=True),
    )
    return CHOOSE_TASK


@auth_wrap
async def reset(update: Update, context: CallbackContext.DEFAULT_TYPE) -> int:
    """End Conversation by command."""

    await update.message.reply_text("See you next time. Type anything to get started.")

    return RESET_CONVERSATION


@auth_wrap
async def choose_task(update: Update, context: CallbackContext) -> int:
    """Choose between download a movie, get download progress, upload activity
        or download my viewing activity"""

    if update.message.text == menu_keyboard[0][0]:
        message = 'Great, give me an IMDB id, a title or an IMDB link.'
        await update.message.reply_text(message)
        return DOWNLOAD_MOVIE

    elif update.message.text == menu_keyboard[1][0]:
        await update.effective_message.reply_text('Ok, retrieving data... (might be slow sometimes)')
        context.user_data['download_progress'] = 0
        return await get_download_progress(update, context)

    elif update.message.text == menu_keyboard[2][0]:
        await update.message.reply_photo(photo=open(TELEGRAM_NETFLIX_PNG, 'rb'),
                                         caption="Ok, follow the instructions, "
                                                 "hit `Download all` and upload here the resulting .csv.\n"
                                                 "You may add any other records to "
                                                 "the CSV, given that you don't change the column names.\n"
                                                 "If you want to also add ratings, create an extra column "
                                                 "named 'Ratings' and it will be picked up.\n"
                                                 "Any overlapping ratings/seen dates will be overwritten. However, "
                                                 "IMDB ratings, seen dates and PLEX seen dates will have prevalence.\n"
                                                 "☢️☢️!! If these titles are not rated in the CSV you'll receive "
                                                 "notifications to rate all of them.\n\n"
                                                 "Choose Yes/No if you want to receive these notifications",
                                         reply_markup=ReplyKeyboardMarkup(bool_keyboard, one_time_keyboard=True,
                                                                          resize_keyboard=True))
        return UPLOAD_ACTIVITY
    elif update.message.text == menu_keyboard[2][1]:
        await update.message.reply_text("Ok, we've started the process, we'll let you know once it's done.")
        return echo
        # return download_csv(update, context)
    return await reset(update, context)


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

    await update.message.reply_text("Just a sec until we get data about this title...")
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
        if 'https://' in update.message.text:
            await update.effective_message.reply_text("Couldn't find the specified ID in the link, are you"
                                                      "sure it's an IMDB link? Try pasting only the ID, as in"
                                                      "`tt0903624`.")
            return DOWNLOAD_MOVIE
        else:
            # Test for title
            movies = search_imdb_title(update.message.text)
            context.user_data['potential_titles'] = movies

            return await choose_multiple(update, context)


@auth_wrap
async def choose_multiple(update: Update, context: CallbackContext) -> int:
    """Loop through potential movie matches"""

    movies = context.user_data['potential_titles']
    if movies:
        if type(movies) == str:
            await update.effective_message.reply_text("We're having trouble with our IMDB API, please"
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
            return await choose_multiple(update, context)
    else:
        await update.effective_message.reply_text("Couldn't find the specified movie."
                                                  " Check your spelling or try pasting the IMDB id or a link"
                                                  "`tt0903624`.")
        return DOWNLOAD_MOVIE


@auth_wrap
async def accept_reject_title(update: Update, context: CallbackContext) -> int:
    """Accept, reject the match or exit"""

    if update.message.text == 'Yes':
        return await check_movie_status(update, context)
    elif update.message.text == 'No':
        if context.user_data['potential_titles']:
            await update.effective_message.reply_text("Ok, trying next hit...")
            return await choose_multiple(update, context)
        else:
            await update.effective_message.reply_text("These were all the hits. Sorry. Feel free to type anything "
                                                      "to start again")
            return RESET_CONVERSATION
    elif update.message.text == 'Exit':
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

    await update.message.reply_text('Searching for available torrents...')
    torrents = get_torrents_for_imdb_id(context.user_data['pkg']['imdb'])
    torrents = sorted(torrents, key=lambda k: k['size'])
    if torrents:
        context.user_data['pkg']['torrents'] = sorted(torrents, key=lambda k: k['size'])
        keyboard = [[]]
        """
        # Check if we need to filter excluded resolutions
        # Removed functionality, left here for reference or other further uses
        if 'from_watchlist' in context.user_data.keys():
            movie_id = deconvert_imdb_id(torrents[0]['imdb'])
            excluded_resolutions = get_excluded_resolutions(movie_id, update.effective_user['id'])
            torrents = [x for x in torrents if x['id'] not in excluded_resolutions]
        """
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
        return await search_for_torrents(update, context)
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
                                                       "on this title.")
    return await reset(update, context)


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


@auth_wrap
async def get_download_progress(update: Update, context: CallbackContext) -> int:
    """Return the status for the last 10 torrents for this user"""
    # TODO maybe make it look a bit better

    user = update.effective_user['id']
    torrents = get_progress(user, logger=logger)
    for torrent in torrents[:5]:
        await update.message.reply_text(f"{torrent['TorrentName']}\n"
                                        f"Resolution: {torrent['Resolution']}\n"
                                        f"Status: {torrent['Status']}\n"
                                        f"Progress: {torrent['Progress']}\n"
                                        f"ETA: {torrent['ETA']}")
    return await reset(update, context)


"""<< UPLOAD ACTIVITY >>"""


@auth_wrap
async def netflix_rate_or_not(update: Update, context: CallbackContext) -> int:
    """User chooses to receive or not notifications for unrated titles."""

    if update.message.text == 'No':
        context.user_data['send_notifications'] = False
    else:
        context.user_data['send_notifications'] = True
    await update.message.reply_text("K, now upload the .csv file please.")
    return NETFLIX_CSV


@auth_wrap
async def netflix_no_rate_option(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text("Choose Yes or No, bro.")
    return UPLOAD_ACTIVITY


@auth_wrap
async def netflix_csv(update: Update, context: CallbackContext) -> int:
    """Sends CSV file in order to be processed"""
    # TODO make job not blocking (used to be not blocking but libray is not
    #  using multithreading.

    csv_context = {
        'user': update.effective_user.id,
        'file': update.message.document.file_id,
        'send_notifications': context.user_data['send_notifications'],
    }
    await update.message.reply_text("Thanks!We started the upload process, we'll let you know "
                                    "when it's done or if there's any trouble.")
    context.job_queue.run_once(
        callback=csv_upload_handler,
        context=csv_context,
        when=10
    )
    return await reset(update, context)


@auth_wrap
async def netflix_no_csv(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text("Upload the .csv or hit /reset.")
    return NETFLIX_CSV

















async def echo(update: Update, context: CallbackContext.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text=update.message.text)


async def caps(update: Update, context: CallbackContext):
    text_caps = ' '.join(context.args).upper()
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text_caps)


async def inline_caps(update: Update, context: CallbackContext.DEFAULT_TYPE):
    query = update.inline_query.query
    if not query:
        return
    results = []
    results.append(
        InlineQueryResultArticle(
            id=query.upper(),
            title='Caps',
            input_message_content=InputTextMessageContent(query.upper())
        )
    )
    await context.bot.answer_inline_query(update.inline_query.id, results)


async def unknown(update: Update, context: CallbackContext.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Sorry, I didn't understand that command.")


if __name__ == '__main__':
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    download_movie_conversation_handler = ConversationHandler(
        entry_points=[
            CommandHandler(
                "reset", reset
            ),
            MessageHandler(
                filters.Regex('^([tT]{2})?\d+$'), parse_imdb_id
            ),
            MessageHandler(
                filters.TEXT, parse_imdb_text
            ),
        ],
        states={
            CHOOSE_MULTIPLE: [
                MessageHandler(
                    filters.TEXT, choose_multiple
                )
            ],
            CHOOSE_ONE: [
                MessageHandler(
                    filters.TEXT, accept_reject_title
                )
            ],
            CONFIRM_REDOWNLOAD_ACTION: [
                MessageHandler(
                    filters.TEXT, confirm_redownload_action
                )
            ],
            SEARCH_FOR_TORRENTS: [
                MessageHandler(
                    filters.TEXT, search_for_torrents
                )
            ],
            DOWNLOAD_TORRENT: [
                CallbackQueryHandler(
                    download_torrent
                )
            ],
            WATCHLIST_NO_TORR: [
                MessageHandler(
                    filters.TEXT, add_to_watchlist_no_torrent
                ),
            ],
        },
        fallbacks=[CommandHandler("reset", reset)],
        map_to_parent={
            DOWNLOAD_MOVIE: DOWNLOAD_MOVIE,
            RESET_CONVERSATION: RESET_CONVERSATION
        }
    )

    check_progress_conversation_handler = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.TEXT, get_download_progress
            ),
            CallbackQueryHandler(
                get_download_progress
            )
        ],
        states={},
        fallbacks=[],
        map_to_parent={
            RESET_CONVERSATION: RESET_CONVERSATION,
        }
    )

    upload_activity_conversation_handler = ConversationHandler(
        entry_points=[
            CommandHandler('reset', reset),
            MessageHandler(
                filters.Regex("^Yes$|^No$"), netflix_rate_or_not,
            ),
            MessageHandler(
                filters.TEXT, netflix_no_rate_option
            ),
        ],
        states={
            NETFLIX_CSV: [
                CommandHandler('reset', reset),
                MessageHandler(
                    filters.Document.FileExtension('csv'), netflix_csv
                ),
                MessageHandler(
                    filters.TEXT, netflix_no_csv
                ),
            ],
        },
        fallbacks=[CommandHandler("reset", reset)],
        map_to_parent={
            UPLOAD_ACTIVITY: UPLOAD_ACTIVITY,
            RESET_CONVERSATION: RESET_CONVERSATION
        }
    )

    conversation_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT, start)],
        states={
            CHOOSE_TASK: [MessageHandler(filters.TEXT, choose_task)],
            DOWNLOAD_MOVIE: [download_movie_conversation_handler],
            CHECK_PROGRESS: [check_progress_conversation_handler],
            UPLOAD_ACTIVITY: [upload_activity_conversation_handler],
            RATE_TITLE: [MessageHandler(filters.TEXT & (~filters.COMMAND), echo)],
            RESET_CONVERSATION: [MessageHandler(filters.TEXT, start)]
        },
        fallbacks=[CommandHandler("reset", reset)]
    )

    # start_handler = CommandHandler('start', start)
    # echo_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), echo)
    # caps_handler = CommandHandler('caps', caps)
    # inline_caps_handler = InlineQueryHandler(inline_caps)
    # unknown_handler = MessageHandler(filters.COMMAND, unknown)

    application.add_handler(conversation_handler)
    """    
    application.add_handler(start_handler)
    application.add_handler(echo_handler)
    application.add_handler(caps_handler)
    application.add_handler(inline_caps_handler)
    application.add_handler(unknown_handler)
    """

    application.run_polling()
