from bot.handlers.utils import (
    get_or_create_user, get_chat_id_from_update, safe_edit_or_send_message, format_task_info,
    check_permissions, show_task_progress
)
from bot.handlers.commands import tasks_command_logic
from bot import bot, logger
from bot.models import User, Task, Subtask
from bot.keyboards import (
    get_task_actions_markup, get_subtask_toggle_markup,
    TASK_MANAGEMENT_MARKUP
)
from telebot.types import Message, CallbackQuery
from django.core.exceptions import ObjectDoesNotExist




def tasks_back_callback(call: CallbackQuery) -> None:
    tasks_command_logic(call)


def main_menu_callback(call: CallbackQuery) -> None:
    chat_id = get_chat_id_from_update(call)
    user = get_or_create_user(chat_id)
    text = "🏠 Главное меню"
    from bot.keyboards import get_main_menu
    safe_edit_or_send_message(call.message.chat.id, text, reply_markup=get_main_menu(user), message_id=call.message.message_id)
