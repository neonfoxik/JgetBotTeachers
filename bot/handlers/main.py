from bot.handlers.utils import (
    get_or_create_user, get_chat_id_from_update, safe_edit_or_send_message, format_task_info,
    check_permissions, show_task_progress
)
from bot import bot, logger
from bot.models import User, Task, Subtask
from bot.keyboards import (
    get_task_actions_markup, get_subtask_toggle_markup,
    TASK_MANAGEMENT_MARKUP
)
from telebot.types import Message, CallbackQuery
from django.core.exceptions import ObjectDoesNotExist




@bot.callback_query_handler(func=lambda c: c.data == "tasks_back")
def tasks_back_callback(call: CallbackQuery) -> None:
    tasks_command_logic(call)


@bot.callback_query_handler(func=lambda c: c.data == "main_menu")
def main_menu_callback(call: CallbackQuery) -> None:
    text = "🏠 Главное меню"
    safe_edit_or_send_message(call.message.chat.id, text, reply_markup=TASK_MANAGEMENT_MARKUP, message_id=call.message.message_id)
