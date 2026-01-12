import logging
import telebot
from django.conf import settings
commands = settings.BOT_COMMANDS
bot = telebot.TeleBot(
    settings.BOT_TOKEN,
    threaded=False,
    skip_pending=True,
)
bot.set_my_commands(commands)
try:
    bot_info = bot.get_me()
    logging.info(f'@{bot_info.username} started successfully')
except Exception as e:
    logging.error(f'Failed to get bot info: {e}')
logger = telebot.logger
logger.setLevel(logging.INFO)
logging.basicConfig(level=logging.INFO, filename="ai_log.log", filemode="w")