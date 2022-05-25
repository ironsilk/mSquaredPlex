import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CallbackContext, CommandHandler
from command_regex_handler import RegexpCommandHandler

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


async def start(update: Update, context: CallbackContext.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="I'm a bot, please talk to me!")


async def regexyey(update: Update, context: CallbackContext.DEFAULT_TYPE, *other_args):
    print('Passed arguments', other_args, type(other_args))
    print(other_args[0])
    await context.bot.send_message(chat_id=update.effective_chat.id, text="worked")


if __name__ == '__main__':
    application = ApplicationBuilder().token('1940395527:AAF1Orhib5d6QvtIMtiOS8WaHWZfN8IrI2Y').build()

    start_handler = CommandHandler('start', start)
    application.add_handler(RegexpCommandHandler(r'WatchMatch_[\d]+', regexyey))
    application.add_handler(start_handler)

    application.run_polling()