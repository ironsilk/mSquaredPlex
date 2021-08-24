import logging
from db_tools import get_movie_from_all_databases
from telegram import ForceReply
from telegram import (
    ReplyKeyboardMarkup,
    Update,
)
from telegram.ext import Updater, MessageHandler, Filters, CallbackContext, ConversationHandler

# Enable logging
logging.basicConfig(
    format='[%(asctime)s] {%(filename)s:%(lineno)d} [%(name)s] [%(levelname)s] --> %(message)s', level=logging.INFO
)

logger = logging.getLogger('MovieTimeBot')

# Stages
IDENTIFY_MOVIE, CHOOSE_MOVIE, CONFIRM_ACTION = range(3)

# Keyboards
menu_keyboard = [
    ["💵 Download a movie"],
    ["📈 Check progress"],
]
bool_keyboard = [
    ['Yes'],
    ['No']
]


def start(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    update.message.reply_markdown_v2(
        fr'Hi {user.mention_markdown_v2()}\!',
        reply_markup=ForceReply(selective=True),
    )


def choose_task(update: Update, context: CallbackContext) -> None:
    if update.message.text == menu_keyboard[0][0]:
        message = 'Great, give me an IMDB id, a title or an IMDB link.'
        update.message.reply_text(message)
        return IDENTIFY_MOVIE

    if update.message.text == menu_keyboard[1][0]:
        message = 'Not implemented yet'
        update.message.reply_text(message)

    message = "Please select one of the options."
    update.effective_message.reply_text(
        message, reply_markup=ReplyKeyboardMarkup(menu_keyboard, one_time_keyboard=True, resize_keyboard=True)
    )


def parse_imdb_id(update: Update, context: CallbackContext) -> int:
    logger.info(f"In parse_imdb_id with package {update.message.text}")
    user_data = context.user_data
    # We need number so filter out the number from the user input:
    imdb_id = ''.join([x for x in update.message.text if x.isdigit()]).lstrip('0')

    # Get IMDB data
    pkg = get_movie_from_all_databases(imdb_id)
    user_data['pkg'] = pkg

    message = f"<a href='{pkg['poster']}'>Is this your movie?\n{pkg['title']}</a>"
    update.effective_message.reply_html(message, reply_markup=ReplyKeyboardMarkup(bool_keyboard,
                                                                                  one_time_keyboard=True,
                                                                                  resize_keyboard=True,
                                                                                  ))
    return CHOOSE_MOVIE


def parse_imdb_link(update: Update, context: CallbackContext) -> int:
    """Ask the user for info about the selected predefined choice."""
    text = update.message.text
    print(text)
    update.message.reply_text(f'Your {text.lower()}? imdb_link')
    return CHOOSE_MOVIE


def parse_imdb_title(update: Update, context: CallbackContext) -> int:
    if update.message.text == 'suka':
        update.message.reply_text("exit")
    """Ask the user for info about the selected predefined choice."""
    text = update.message.text
    print('parse_imdb_title')
    # update.message.reply_text(f'Your {text.lower()}? title')
    return CHOOSE_MOVIE


def accept_reject_title(update: Update, context: CallbackContext) -> int:
    if update.message.text == 'Yes':
        # Warn the user if movie is already in DB and if's already downloaded - need to search for the torrent also.
        # TODO change my_movies table to have an autoincrement primary key or change tables altogether.
        update.message.reply_text("Searching for available torrents...")
        # check if torrent is already downloaded

        # search for torrents on FL

    else:
        update.message.reply_text("Please re-enter your search query or type 'suka' to exit")
        return IDENTIFY_MOVIE
    print(context.user_data)
    print('accept reject')
    print(update.message.text)
    return confirm_action(update, context)


def confirm_action(update: Update, context: CallbackContext) -> int:
    update.message.reply_text('Download request in progress...')


def echo(update: Update, context: CallbackContext) -> None:
    """Echo the user message."""
    print(update.message.text)
    update.message.reply_text(update.message.text)


def main() -> None:
    """Start the bot."""
    # Create the Updater and pass it your bot's token.
    updater = Updater("1940395527:AAF1Orhib5d6QvtIMtiOS8WaHWZfN8IrI2Y")

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    # on different commands - answer in Telegram
    # dispatcher.add_handler(CommandHandler("start", choose_task))
    # dispatcher.add_handler(CommandHandler("help", help_command))

    # on non command i.e message - echo the message on Telegram
    # dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, choose_task))

    # Add conversation handler with the states IDENTIFY_MOVIE, TYPING_CHOICE and TYPING_REPLY
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(Filters.text & ~Filters.command, choose_task)],
        states={
            IDENTIFY_MOVIE: [
                MessageHandler(
                    Filters.regex('^([tT]{2})?\d+$'), parse_imdb_id
                ),
                MessageHandler(
                    Filters.regex('[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)'),
                    parse_imdb_link
                ),
                MessageHandler(
                    Filters.text(Filters.text), parse_imdb_title
                ),
            ],
            CHOOSE_MOVIE: [
                MessageHandler(
                    Filters.text, accept_reject_title
                )
            ],
            CONFIRM_ACTION: [
                MessageHandler(
                    Filters.text, confirm_action
                )
            ],
        },
        fallbacks=[MessageHandler(Filters.regex('^Done$'), echo)],
    )
    dispatcher.add_handler(conv_handler)
    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()
