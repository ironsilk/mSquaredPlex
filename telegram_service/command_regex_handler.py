import re

from telegram import Update
from telegram.ext import Handler


class RegexpCommandHandler(Handler):
    def __init__(self, command_regexp, callback, separator="_", allow_edited=True, pass_args=True):

        super().__init__(callback)
        self.command_regexp = command_regexp
        self.separator = separator
        self.allow_edited = allow_edited
        self.pass_args = pass_args

    def check_update(self, update):
        """
        This method is called to determine if an update should be handled by this handler instance.
        """

        if (isinstance(update, Update)
                and (update.message or update.edited_message and self.allow_edited)):
            message = update.message or update.edited_message
            if message.text and message.text.startswith('/') and len(message.text) > 1:
                command = message.text[1:].split(None, 1)[0].split('@')
                command.append(
                    update.effective_user.username)  # in case the command was send without a username
                match = re.match(self.command_regexp, command[0])

                return True and (bool(match) and command[1].lower() == update.effective_user.username.lower())
            else:
                return False

        else:
            return False

    async def handle_update(self, update, application, check_result, context):
        """
        This method is called if it was determined that an update should indeed be handled by this instance.
        Splits the command by the defined separator and returns arguments.
        """
        if self.pass_args:
            message = update.message or update.edited_message
            optional_args = message.text.split(self.separator)[1:]
        else:
            optional_args = []
        return await self.callback(update, context, *optional_args)
