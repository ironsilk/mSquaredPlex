import logging
import re
from pprint import pprint

from telegram import (
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Update,
)
from telegram.ext import Updater, MessageHandler, Filters, CallbackContext, ConversationHandler, CallbackQueryHandler
from transmission_rpc.error import TransmissionError

from db_tools import get_movie_from_all_databases
from torr_tools import get_torrents_for_imdb_id, send_torrent, compose_link
from utils import search_imdb_title

# Enable logging
logging.basicConfig(
    format='[%(asctime)s] {%(filename)s:%(lineno)d} [%(name)s] [%(levelname)s] --> %(message)s', level=logging.INFO
)

logger = logging.getLogger('MovieTimeBot')

# Stages
CHOOSE_TASK, IDENTIFY_MOVIE, CHOOSE_MULTIPLE, CHOOSE_ONE, CONFIRM_REDOWNLOAD_ACTION, SEARCH_FOR_TORRENTS, \
DOWNLOAD_TORRENT = range(7)

# Keyboards
menu_keyboard = [
    ["💵 Download a movie"],
    ["📈 Check progress"],
]
bool_keyboard = [
    ['Yes'],
    ['No']
]


def start(update: Update, context: CallbackContext) -> int:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    update.message.reply_markdown_v2(
        f"Hi {user.mention_markdown_v2()}\!\n"
        f"Please select one of the options",
        reply_markup=ReplyKeyboardMarkup(menu_keyboard, one_time_keyboard=True, resize_keyboard=True),
    )
    return CHOOSE_TASK


def choose_task(update: Update, context: CallbackContext) -> int:
    if update.message.text == menu_keyboard[0][0]:
        message = 'Great, give me an IMDB id, a title or an IMDB link.'
        update.message.reply_text(message)
        return IDENTIFY_MOVIE

    elif update.message.text == menu_keyboard[1][0]:
        message = 'Not implemented yet'
        update.message.reply_text(message)

    # If the user doesnt click any options, do nothing?
    elif update.message.text == 'suka':
        return bail(update, context)

    else:
        if 'dont_greet' in context.user_data:
            update.message.reply_text(
                f"Please select one of the options",
                reply_markup=ReplyKeyboardMarkup(menu_keyboard, one_time_keyboard=True, resize_keyboard=True),
            )
            return CHOOSE_TASK
        else:
            return start(update, context)


def parse_imdb_id(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("Just a sec until we get data about this title...")
    # We need number so filter out the number from the user input:
    imdb_id = ''.join([x for x in update.message.text if x.isdigit()]).lstrip('0')

    # Get IMDB data
    pkg = get_movie_from_all_databases(imdb_id)
    context.user_data['pkg'] = pkg
    context.user_data['more_options'] = False

    message = f"<a href='{pkg['poster']}'>Is this your movie?\n{pkg['title']}</a>"
    update.effective_message.reply_html(message, reply_markup=ReplyKeyboardMarkup(bool_keyboard,
                                                                                  one_time_keyboard=True,
                                                                                  resize_keyboard=True,
                                                                                  ))
    return CHOOSE_ONE


def parse_imdb_text(update: Update, context: CallbackContext) -> int:
    # https://www.w3resource.com/mysql/string-functions/mysql-soundex-function.php
    # https://stackoverflow.com/questions/2602252/mysql-query-string-contains
    update.message.reply_text("Just a sec until we get data about this title...")
    # Is it a link?
    try:
        imdb_id = re.search("([tT]{2})?\d+", update.message.text).group(0)

        # We need number so filter out the number from the user input:
        imdb_id = ''.join([x for x in imdb_id if x.isdigit()]).lstrip('0')

        # Get IMDB data
        pkg = get_movie_from_all_databases(imdb_id)
        context.user_data['pkg'] = pkg

        message = f"<a href='{pkg['poster']}'>Is this your movie?\n{pkg['title']}</a>"
        update.effective_message.reply_html(message, reply_markup=ReplyKeyboardMarkup(bool_keyboard,
                                                                                      one_time_keyboard=True,
                                                                                      resize_keyboard=True,
                                                                                      ))
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
            if movies:
                # Test for IMDB API ERROR
                if type(movies) == str:
                    update.effective_message.reply_text("We're having trouble with our IMDB API, please"
                                                        "insert an IMDB ID or paste a link.")
                    return IDENTIFY_MOVIE
                # No error, we have matches
                else:
                    movies = [get_movie_from_all_databases(x['id']) for x in movies]
                    movies = [x for x in movies if x]
                    update.effective_message.reply_text(f"We found {len(movies)} potential matches:")
                    pprint(movies)
                    if movies:
                        keyboard = [[]]
                        for pos, item in enumerate(movies):
                            # pprint(pos, item)
                            pos += 1  # exclude 0
                            btn_text = f"Name: {str(item['primaryTitle'])}\n" \
                                       f"Year: {str(item['startYear'])}\n" \
                                       f"IMDB/ROTT/TMDB: {str(item['averageRating'])}/{str(item['rott_score'])}" \
                                       f"/{str(item['tmdb_score'])}\n" \
                                       f"Cast: {item['cast']}\n" \
                                       f"Trailer: {item['trailer_link']}"
                            btn = InlineKeyboardButton(btn_text, callback_data=item['imdb'])
                            keyboard.append([btn])
                        # Add button for None
                        keyboard.append([InlineKeyboardButton('None, thanks', callback_data=0)])
                        update.message.reply_text(
                            f"Is your movie here?",
                            reply_markup=InlineKeyboardMarkup(keyboard, one_time_keyboard=True),
                        )
                        return DOWNLOAD_TORRENT

            update.effective_message.reply_text("Couldn't find the specified movie,"
                                                "Try pasting the IMDB id or a link"
                                                "`tt0903624`.")
            return IDENTIFY_MOVIE


def choose_multiple(update: Update, context: CallbackContext) -> int:
    print('in choose multiple')
    movies = context.user_data['potential_titles']
    if movies:
        print(movies)
        movie = movies.pop(0)
        # Check again if we can find it
        pkg = get_movie_from_all_databases(movie['id'])
        # context.user_data['pkg'] = pkg
        if pkg:
            context.user_data['pkg'] = pkg

            message = f"<a href='{pkg['poster']}'>Is this your movie?\n{pkg['title']}</a>"
            update.effective_message.reply_html(message, reply_markup=ReplyKeyboardMarkup(bool_keyboard,
                                                                                          one_time_keyboard=True,
                                                                                          resize_keyboard=True,
                                                                                          ))
            return accept_reject_title(update, context)
        else:
            return choose_multiple(update, context)
    else:
        update.effective_message.reply_text("Couldn't find the specified movie,"
                                            "Try pasting the IMDB id or a link"
                                            "`tt0903624`.")
        return IDENTIFY_MOVIE


def return_parsed_id(update: Update, context: CallbackContext, movie) -> int:
    context.user_data['pkg'] = movie

    message = f"<a href='{movie['poster']}'>Is this your movie?\n{movie['title']}</a>"
    update.effective_message.reply_html(message, reply_markup=ReplyKeyboardMarkup(bool_keyboard,
                                                                                  one_time_keyboard=True,
                                                                                  resize_keyboard=True,
                                                                                  ))
    return CHOOSE_ONE


def accept_reject_title(update: Update, context: CallbackContext) -> int:
    print('accept', update.message.text)
    movie = context.user_data['pkg']
    if update.message.text == 'Yes':
        check_movie_status(update, context)
    else:
        if context.user_data['potential_titles']:
            update.effective_message.reply_text("Ok, trying next hit...")
            return CHOOSE_MULTIPLE
        else:
            return bail(update, context)


def check_movie_status(update: Update, context: CallbackContext) -> int:
    movie = context.user_data['pkg']
    # Check if you've already seen it and send info
    if movie['already_in_my_movies']:
        message = f"Movie already in your DB."
        if movie['my_score']:
            message += f"\nYour score: {movie['my_score']}"
        if movie['seen_date']:
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


def confirm_redownload_action(update: Update, context: CallbackContext) -> int:
    if update.message.text == 'Yes':
        return search_for_torrents(update, context)
    else:
        return bail(update, context)


def search_for_torrents(update: Update, context: CallbackContext) -> int:
    update.message.reply_text('Searching for available torrents...')
    torrents = get_torrents_for_imdb_id(context.user_data['pkg']['imdb'])

    if torrents:
        keyboard = [[]]
        for pos, item in enumerate(torrents):
            pos += 1  # exclude 0
            btn_text = f"Quality: {str(item['resolution'])}||" \
                       f"Size: {str(round(item['size'] / 1000000000, 2))}\n" \
                       f"S/P: {str(item['seeders'])}/{str(item['leechers'])}"
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
            "What would you like to do next?",
            reply_markup=ReplyKeyboardMarkup(menu_keyboard, one_time_keyboard=True, resize_keyboard=True),
        )
        return CHOOSE_TASK


def download_torrent(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    if query.data != '0':
        query.edit_message_text(text=f"Thanks, sending download request...")
        # Send download request
        try:
            send_torrent(compose_link(query.data))
            message = f"Download started, have a great day!"
        except TransmissionError as e:
            raise (e)
            message = f"Download failed, please check logs and try again."
        query.answer()
        query.edit_message_text(text=message)
        return ConversationHandler.END
    else:
        query.answer()
        query.edit_message_text(text="Ok, have a great day!")
        return ConversationHandler.END


def echo(update: Update, context: CallbackContext) -> None:
    """Echo the user message."""
    print(update.message.text)
    update.message.reply_text(update.message.text)


def bail(update: Update, context: CallbackContext) -> int:
    if update.message.text == 'suka':
        context.user_data.clear()
        update.message.reply_text("Ok, have a great day!")
        return ConversationHandler.END
    update.message.reply_text("Please re-enter your search query or type 'suka' to exit")
    context.user_data.clear()
    return IDENTIFY_MOVIE


def go_back(update, context, message):
    update.message.reply_text(message)
    context.user_data.clear()
    context.user_data['dont_greet'] = True
    return choose_task(update, context)


def main() -> None:
    """Start the bot."""
    # Create the Updater and pass it your bot's token.
    updater = Updater("1940395527:AAF1Orhib5d6QvtIMtiOS8WaHWZfN8IrI2Y")

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(Filters.text & ~Filters.command, start)],
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
        },
        fallbacks=[MessageHandler(Filters.regex('^Done$'), echo)],
    )
    dispatcher.add_handler(conv_handler)

    # Start the Bot
    updater.start_polling()

    updater.idle()


if __name__ == '__main__':
    main()
