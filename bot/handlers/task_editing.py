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

    # Для завершенных задач добавляем кнопку "Сделать незавершенной"
    if task.status == 'completed':
        markup.add(InlineKeyboardButton("🔄 Сделать незавершенной", callback_data=f"reopen_task_{task.id}"))

    markup.add(InlineKeyboardButton("📝 Название", callback_data=f"edit_title_{task.id}"))
    markup.add(InlineKeyboardButton("📖 Описание", callback_data=f"edit_description_{task.id}"))
    markup.add(InlineKeyboardButton("👤 Исполнитель", callback_data=f"edit_assignee_{task.id}"))
    markup.add(InlineKeyboardButton("⏰ Срок", callback_data=f"edit_due_date_{task.id}"))
    markup.add(InlineKeyboardButton("⬅️ Назад", callback_data=f"task_progress_{task.id}"))
    safe_edit_or_send_message(call.message.chat.id, text, reply_markup=markup, message_id=call.message.message_id)


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


def edit_due_date_callback(call: CallbackQuery) -> None:
    try:
        task_id = int(call.data.split('_')[2])
        task = Task.objects.get(id=task_id)
        chat_id = get_chat_id_from_update(call)
        allowed, error_msg = check_permissions(chat_id, task, require_creator=True)
        if not allowed:
            bot.answer_callback_query(call.id, error_msg, show_alert=True)
            return

        # Показываем календарь вместо текстового ввода
        from bot.handlers.calendar import show_calendar
        show_calendar(chat_id, f"task_editing_{task_id}", call.message.message_id)

    except (ValueError, ObjectDoesNotExist):
        bot.answer_callback_query(call.id, "Задача не найдена", show_alert=True)


def add_subtasks_callback(call: CallbackQuery) -> None:
    try:
        task_id = int(call.data.split('_')[2])
        task = Task.objects.get(id=task_id)
        chat_id = get_chat_id_from_update(call)
        allowed, error_msg = check_permissions(chat_id, task, require_creator=True)
        if not allowed:
            bot.answer_callback_query(call.id, error_msg, show_alert=True)
            return

        if task.status == 'completed':
            bot.answer_callback_query(call.id, "Нельзя добавлять подзадачи к завершенной задаче", show_alert=True)
            return

        text = f"📋 ДОБАВЛЕНИЕ ПОДЗАДАЧ\n\nЗадача: {task.title}\n\nВведите названия подзадач, каждую с новой строки:"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("⬅️ Отмена", callback_data=f"task_progress_{task_id}"))
        safe_edit_or_send_message(call.message.chat.id, text, reply_markup=markup, message_id=call.message.message_id)

        # Устанавливаем состояние пользователя для ожидания подзадач
        user_state = {'adding_subtasks_task_id': task_id}
        set_user_state(chat_id, user_state)

        # Подтверждаем callback
        bot.answer_callback_query(call.id)

    except (ValueError, ObjectDoesNotExist) as e:
        logger.error(f"Error in add_subtasks_callback: {e}")
        bot.answer_callback_query(call.id, "Задача не найдена", show_alert=True)
    except Exception as e:
        logger.error(f"Unexpected error in add_subtasks_callback: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка", show_alert=True)


def reopen_task_callback(call: CallbackQuery) -> None:
    try:
        task_id = int(call.data.split('_')[2])
        task = Task.objects.get(id=task_id)
        chat_id = get_chat_id_from_update(call)
        allowed, error_msg = check_permissions(chat_id, task, require_creator=True)
        if not allowed:
            bot.answer_callback_query(call.id, error_msg, show_alert=True)
            return

        if task.status != 'completed':
            bot.answer_callback_query(call.id, "Задача уже незавершена", show_alert=True)
            return

        # Меняем статус задачи на active и очищаем дату закрытия
        task.status = 'active'
        task.closed_at = None
        task.save()

        text = f"✅ Задача '{task.title}' снова стала активной и доступной для редактирования"
        safe_edit_or_send_message(call.message.chat.id, text, reply_markup=TASK_MANAGEMENT_MARKUP, message_id=call.message.message_id)

        # Уведомляем исполнителя, если он не создатель
        if task.creator.telegram_id != task.assignee.telegram_id:
            try:
                bot.send_message(
                    task.assignee.telegram_id,
                    f"🔄 ЗАДАЧА СНОВА АКТИВНА\n\n{format_task_info(task)}\n\nЗадача была reopened создателем."
                )
            except Exception as e:
                logger.error(f"Не удалось уведомить исполнителя задачи {task_id}: {e}")

        # Подтверждаем callback
        bot.answer_callback_query(call.id)

    except (ValueError, ObjectDoesNotExist) as e:
        logger.error(f"Error in reopen_task_callback: {e}")
        bot.answer_callback_query(call.id, "Задача не найдена", show_alert=True)
    except Exception as e:
        logger.error(f"Unexpected error in reopen_task_callback: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка", show_alert=True)