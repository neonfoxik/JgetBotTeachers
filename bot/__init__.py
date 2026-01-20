import logging
from django.conf import settings

# Lazy initialization of bot to avoid import issues during Django setup
_bot = None
_logger = None

def get_bot():
    """Lazy initialization of the bot"""
    global _bot
    if _bot is None:
        import telebot
        from dd.settings import get_bot_commands

        commands = get_bot_commands()
        _bot = telebot.TeleBot(
            settings.BOT_TOKEN,
            threaded=False,
            skip_pending=True,
        )
        _bot.set_my_commands(commands)
        try:
            bot_info = _bot.get_me()
            logging.info(f'@{bot_info.username} started successfully')
        except Exception as e:
            logging.error(f'Failed to get bot info: {e}')
    return _bot

def get_logger():
    """Lazy initialization of the logger"""
    global _logger
    if _logger is None:
        import telebot
        _logger = telebot.logger
        _logger.setLevel(logging.INFO)
        logging.basicConfig(level=logging.INFO, filename="ai_log.log", filemode="w")
    return _logger

# Provide backwards compatibility
def __getattr__(name):
    if name == 'bot':
        return get_bot()
    elif name == 'logger':
        return get_logger()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")