from bot.handlers.utils import (
    get_or_create_user, get_chat_id_from_update, safe_edit_or_send_message, format_task_info,
    check_permissions
)
from bot import bot, logger
from bot.models import User, Task
from bot.keyboards import (
    get_task_actions_markup, get_user_selection_markup,
    TASK_MANAGEMENT_MARKUP
)
from telebot.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from django.core.exceptions import ObjectDoesNotExist
from datetime import datetime
from django.utils import timezone


def show_task_edit_menu(call: CallbackQuery, task: Task) -> None:
    text = f"✏️ РЕДАКТИРОВАНИЕ ЗАДАЧИ\n\n{format_task_info(task)}\n\nВыберите что редактировать:"
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📝 Название", callback_data=f"edit_title_{task.id}"))
    markup.add(InlineKeyboardButton("📖 Описание", callback_data=f"edit_description_{task.id}"))
    markup.add(InlineKeyboardButton("👤 Исполнитель", callback_data=f"edit_assignee_{task.id}"))
    markup.add(InlineKeyboardButton("⏰ Срок", callback_data=f"edit_due_date_{task.id}"))
    markup.add(InlineKeyboardButton("⬅️ Назад", callback_data=f"task_progress_{task.id}"))
    safe_edit_or_send_message(call.message.chat.id, text, reply_markup=markup, message_id=call.message.message_id)


@bot.callback_query_handler(func=lambda c: c.data.startswith("task_edit_"))
def task_edit_callback(call: CallbackQuery) -> None:
    try:
        task_id = int(call.data.split('_')[2])
        task = Task.objects.get(id=task_id)
        chat_id = get_chat_id_from_update(call)
        allowed, error_msg = check_permissions(chat_id, task, require_creator=True)
        if not allowed:
            bot.answer_callback_query(call.id, error_msg, show_alert=True)
            return

        show_task_edit_menu(call, task)

    except (ValueError, ObjectDoesNotExist):
        bot.answer_callback_query(call.id, "Задача не найдена", show_alert=True)


@bot.callback_query_handler(func=lambda c: c.data.startswith("edit_title_"))
def edit_title_callback(call: CallbackQuery) -> None:
    try:
        task_id = int(call.data.split('_')[2])
        task = Task.objects.get(id=task_id)
        chat_id = get_chat_id_from_update(call)
        allowed, error_msg = check_permissions(chat_id, task, require_creator=True)
        if not allowed:
            bot.answer_callback_query(call.id, error_msg, show_alert=True)
            return

        text = f"📝 Введите новое название для задачи:\n\nТекущее: {task.title}"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("⬅️ Отмена", callback_data=f"task_edit_{task_id}"))
        safe_edit_or_send_message(call.message.chat.id, text, reply_markup=markup, message_id=call.message.message_id)

        # Устанавливаем состояние пользователя для ожидания нового названия
        from bot.handlers.utils import set_user_state
        user_state = {'editing_task_id': task_id, 'editing_field': 'title'}
        set_user_state(chat_id, user_state)

    except (ValueError, ObjectDoesNotExist):
        bot.answer_callback_query(call.id, "Задача не найдена", show_alert=True)


@bot.callback_query_handler(func=lambda c: c.data.startswith("edit_description_"))
def edit_description_callback(call: CallbackQuery) -> None:
    try:
        task_id = int(call.data.split('_')[2])
        task = Task.objects.get(id=task_id)
        chat_id = get_chat_id_from_update(call)
        allowed, error_msg = check_permissions(chat_id, task, require_creator=True)
        if not allowed:
            bot.answer_callback_query(call.id, error_msg, show_alert=True)
            return

        current_desc = task.description or "не указано"
        text = f"📖 Введите новое описание для задачи:\n\nТекущее: {current_desc}"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("⬅️ Отмена", callback_data=f"task_edit_{task_id}"))
        safe_edit_or_send_message(call.message.chat.id, text, reply_markup=markup, message_id=call.message.message_id)

        # Устанавливаем состояние пользователя для ожидания нового описания
        from bot.handlers.utils import set_user_state
        user_state = {'editing_task_id': task_id, 'editing_field': 'description'}
        set_user_state(chat_id, user_state)

    except (ValueError, ObjectDoesNotExist):
        bot.answer_callback_query(call.id, "Задача не найдена", show_alert=True)


@bot.callback_query_handler(func=lambda c: c.data.startswith("edit_assignee_"))
def edit_assignee_callback(call: CallbackQuery) -> None:
    try:
        task_id = int(call.data.split('_')[2])
        task = Task.objects.get(id=task_id)
        chat_id = get_chat_id_from_update(call)
        allowed, error_msg = check_permissions(chat_id, task, require_creator=True)
        if not allowed:
            bot.answer_callback_query(call.id, error_msg, show_alert=True)
            return

        show_assignee_selection_page(call, task, 0)

    except (ValueError, ObjectDoesNotExist):
        bot.answer_callback_query(call.id, "Задача не найдена", show_alert=True)


def show_assignee_selection_page(call: CallbackQuery, task: Task, page: int, users_per_page: int = 5) -> None:
    users = list(User.objects.all())
    markup = get_user_selection_markup(users, page, users_per_page)

    # Добавляем кнопку "Назад к редактированию"
    back_button = InlineKeyboardButton("⬅️ Назад к редактированию", callback_data=f"task_edit_{task.id}")
    if markup.keyboard and len(markup.keyboard) > 0:
        markup.keyboard.append([back_button])
    else:
        markup.add(back_button)

    text = f"👤 Выберите нового исполнителя для задачи '{task.title}' (страница {page + 1}):"
    safe_edit_or_send_message(call.message.chat.id, text, reply_markup=markup, message_id=call.message.message_id)


@bot.callback_query_handler(func=lambda c: c.data.startswith("assignee_page_"))
def assignee_page_callback(call: CallbackQuery) -> None:
    try:
        parts = call.data.split('_')
        task_id = int(parts[2])
        page = int(parts[3])

        task = Task.objects.get(id=task_id)
        chat_id = get_chat_id_from_update(call)
        allowed, error_msg = check_permissions(chat_id, task, require_creator=True)
        if not allowed:
            bot.answer_callback_query(call.id, error_msg, show_alert=True)
            return

        show_assignee_selection_page(call, task, page)

    except (ValueError, ObjectDoesNotExist):
        bot.answer_callback_query(call.id, "Задача не найдена", show_alert=True)


@bot.callback_query_handler(func=lambda c: c.data.startswith("change_assignee_"))
def change_assignee_callback(call: CallbackQuery) -> None:
    try:
        parts = call.data.split('_')
        task_id = int(parts[2])
        new_assignee_telegram_id = parts[3]

        task = Task.objects.get(id=task_id)
        chat_id = get_chat_id_from_update(call)
        allowed, error_msg = check_permissions(chat_id, task, require_creator=True)
        if not allowed:
            bot.answer_callback_query(call.id, error_msg, show_alert=True)
            return

        from bot.handlers.utils import get_user_state
        user_state = get_user_state(chat_id)
        if not user_state or new_assignee_telegram_id not in user_state.get('available_users', []):
            bot.answer_callback_query(call.id, "Пользователь не найден в списке", show_alert=True)
            return

        old_assignee = task.assignee
        new_assignee = User.objects.get(telegram_id=new_assignee_telegram_id)
        task.assignee = new_assignee
        task.save()

        # Уведомляем нового исполнителя
        try:
            bot.send_message(
                new_assignee.telegram_id,
                f"📋 ВАМ НАЗНАЧЕНА ЗАДАЧА\n\n{format_task_info(task)}"
            )
        except Exception:
            pass

        from bot.handlers.utils import clear_user_state
        clear_user_state(chat_id)

        text = f"✅ Исполнитель задачи '{task.title}' изменен с {old_assignee.user_name} на {new_assignee.user_name}"
        safe_edit_or_send_message(call.message.chat.id, text, reply_markup=TASK_MANAGEMENT_MARKUP, message_id=call.message.message_id)

    except (ValueError, ObjectDoesNotExist):
        bot.answer_callback_query(call.id, "Ошибка при смене исполнителя", show_alert=True)


@bot.callback_query_handler(func=lambda c: c.data.startswith("edit_due_date_"))
def edit_due_date_callback(call: CallbackQuery) -> None:
    try:
        task_id = int(call.data.split('_')[2])
        task = Task.objects.get(id=task_id)
        chat_id = get_chat_id_from_update(call)
        allowed, error_msg = check_permissions(chat_id, task, require_creator=True)
        if not allowed:
            bot.answer_callback_query(call.id, error_msg, show_alert=True)
            return

        current_due = task.due_date.strftime('%d.%m.%Y %H:%M') if task.due_date else "не установлен"
        text = f"⏰ Введите новый срок для задачи в формате ДД.ММ.ГГГГ ЧЧ:ММ:\n\nТекущий: {current_due}"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Убрать срок", callback_data=f"remove_due_date_{task_id}"))
        markup.add(InlineKeyboardButton("⬅️ Отмена", callback_data=f"task_edit_{task_id}"))
        safe_edit_or_send_message(call.message.chat.id, text, reply_markup=markup, message_id=call.message.message_id)

        # Устанавливаем состояние пользователя для ожидания новой даты
        from bot.handlers.utils import set_user_state
        user_state = {'editing_task_id': task_id, 'editing_field': 'due_date'}
        set_user_state(chat_id, user_state)

    except (ValueError, ObjectDoesNotExist):
        bot.answer_callback_query(call.id, "Задача не найдена", show_alert=True)
