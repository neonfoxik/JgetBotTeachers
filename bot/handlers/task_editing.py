from bot.handlers.utils import (
    get_or_create_user, get_chat_id_from_update, safe_edit_or_send_message, format_task_info,
    check_permissions, check_registration
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
    markup.add(InlineKeyboardButton("👤 Исполнитель", callback_data=f"edit_assignee_choice_{task.id}"))
    markup.add(InlineKeyboardButton("🔔 Уведомления", callback_data=f"edit_notifications_{task.id}"))
    markup.add(InlineKeyboardButton("⏰ Срок", callback_data=f"edit_due_date_{task.id}"))
    markup.add(InlineKeyboardButton("⬅️ Назад", callback_data=f"task_progress_{task.id}"))
    safe_edit_or_send_message(call.message.chat.id, text, reply_markup=markup, message_id=call.message.message_id)


def task_edit_callback(call: CallbackQuery) -> None:
    if not check_registration(call):
        return
    try:
        task_id = int(call.data.split('_')[2])
        task = Task.objects.get(id=task_id)
        chat_id = get_chat_id_from_update(call)
        allowed, error_msg = check_permissions(chat_id, task, require_creator=False)
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
        allowed, error_msg = check_permissions(chat_id, task, require_creator=False)
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
        allowed, error_msg = check_permissions(chat_id, task, require_creator=False)
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


def edit_assignee_choice_callback(call: CallbackQuery) -> None:
    """Выбор: редактировать конкретного исполнителя или роль"""
    try:
        task_id = int(call.data.split('_')[3])
        task = Task.objects.get(id=task_id)
        chat_id = get_chat_id_from_update(call)
        
        text = f"👤 РЕДАКТИРОВАНИЕ ИСПОЛНИТЕЛЯ\n\nЗадача: {task.title}\n\nВыберите тип исполнителя:"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("👤 Конкретный пользователь", callback_data=f"edit_assignee_user_{task_id}"))
        markup.add(InlineKeyboardButton("👥 Роль (группа)", callback_data=f"edit_assignee_role_{task_id}"))
        markup.add(InlineKeyboardButton("⬅️ Назад", callback_data=f"task_edit_{task_id}"))
        safe_edit_or_send_message(chat_id, text, reply_markup=markup, message_id=call.message.message_id)
        
    except (ValueError, ObjectDoesNotExist):
        bot.answer_callback_query(call.id, "Задача не найдена", show_alert=True)

def edit_assignee_user_callback(call: CallbackQuery) -> None:
    """Редактирование конкретного исполнителя"""
    try:
        task_id = int(call.data.split('_')[3])
        task = Task.objects.get(id=task_id)
        chat_id = get_chat_id_from_update(call)
        allowed, error_msg = check_permissions(chat_id, task, require_creator=False)
        if not allowed:
            bot.answer_callback_query(call.id, error_msg, show_alert=True)
            return

        from bot.handlers.utils import set_user_state
        set_user_state(chat_id, {'editing_task_id': task_id, 'editing_field': 'assignee', 'calendar_context': f'task_editing_{task_id}'})
        show_assignee_selection_page(call, task, 0)

    except (ValueError, ObjectDoesNotExist):
        bot.answer_callback_query(call.id, "Задача не найдена", show_alert=True)

def edit_assignee_role_callback(call: CallbackQuery) -> None:
    """Редактирование роли-исполнителя"""
    try:
        task_id = int(call.data.split('_')[3])
        task = Task.objects.get(id=task_id)
        chat_id = get_chat_id_from_update(call)
        
        from bot.models import Role
        roles = Role.objects.all()
        
        text = f"👥 ВЫБОР РОЛИ\n\nВыберите роль для задачи '{task.title}':"
        markup = InlineKeyboardMarkup()
        for role in roles:
            markup.add(InlineKeyboardButton(f"{role.name}", callback_data=f"save_edit_role_{task_id}_{role.id}"))
        
        markup.add(InlineKeyboardButton("⬅️ Назад", callback_data=f"edit_assignee_choice_{task_id}"))
        safe_edit_or_send_message(chat_id, text, reply_markup=markup, message_id=call.message.message_id)
        
    except (ValueError, ObjectDoesNotExist):
        bot.answer_callback_query(call.id, "Задача не найдена", show_alert=True)

def save_edit_role_callback(call: CallbackQuery) -> None:
    """Сохранение выбранной роли"""
    try:
        parts = call.data.split('_')
        task_id = int(parts[3])
        role_id = int(parts[4])
        
        task = Task.objects.get(id=task_id)
        from bot.models import Role
        role = Role.objects.get(id=role_id)
        
        task.assigned_role = role
        task.assignee = None # Сбрасываем конкретного исполнителя
        task.save()
        
        bot.answer_callback_query(call.id, f"✅ Роль изменена на {role.name}")
        show_task_edit_menu(call, task)
        
    except Exception as e:
        logger.error(f"Error saving role edit: {e}")
        bot.answer_callback_query(call.id, "Ошибка при сохранении", show_alert=True)

def edit_notifications_callback(call: CallbackQuery) -> None:
    """Редактирование интервала уведомлений"""
    try:
        task_id = int(call.data.split('_')[2])
        task = Task.objects.get(id=task_id)
        chat_id = get_chat_id_from_update(call)
        
        text = f"🔔 УВЕДОМЛЕНИЯ\n\nВыберите интервал напоминаний для задачи '{task.title}':"
        markup = InlineKeyboardMarkup()
        
        # Кнопки как при создании
        intervals = [
            ("5 мин", 5), ("10 мин", 10), ("15 мин", 15),
            ("30 мин", 30), ("1 час", 60), ("2 часа", 120),
            ("4 часа", 240), ("12 час", 720), ("24 час", 1440)
        ]
        
        row = []
        for i, (label, val) in enumerate(intervals):
            row.append(InlineKeyboardButton(label, callback_data=f"save_edit_notify_{task_id}_{val}"))
            if (i + 1) % 3 == 0:
                markup.row(*row)
                row = []
        if row: markup.row(*row)
        
        markup.add(InlineKeyboardButton("🚫 Без уведомлений", callback_data=f"save_edit_notify_{task_id}_none"))
        markup.add(InlineKeyboardButton("⬅️ Назад", callback_data=f"task_edit_{task_id}"))
        
        safe_edit_or_send_message(chat_id, text, reply_markup=markup, message_id=call.message.message_id)
        
    except (ValueError, ObjectDoesNotExist):
        bot.answer_callback_query(call.id, "Задача не найдена", show_alert=True)

def save_edit_notify_callback(call: CallbackQuery) -> None:
    """Сохранение интервала уведомлений"""
    try:
        parts = call.data.split('_')
        task_id = int(parts[3])
        val_str = parts[4]
        
        task = Task.objects.get(id=task_id)
        task.notification_interval = None if val_str == 'none' else int(val_str)
        task.save()
        
        bot.answer_callback_query(call.id, "✅ Интервал уведомлений обновлен")
        show_task_edit_menu(call, task)
        
    except Exception as e:
        logger.error(f"Error saving notify edit: {e}")
        bot.answer_callback_query(call.id, "Ошибка при сохранении", show_alert=True)


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
        allowed, error_msg = check_permissions(chat_id, task, require_creator=False)
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
        allowed, error_msg = check_permissions(chat_id, task, require_creator=False)
        if not allowed:
            bot.answer_callback_query(call.id, error_msg, show_alert=True)
            return

        from bot.handlers.utils import get_user_state
        user_state = get_user_state(chat_id)
        
        old_assignee = task.assignee
        new_assignee = User.objects.get(telegram_id=new_assignee_telegram_id)
        
        task.assignee = new_assignee
        task.assigned_role = None # Очищаем роль, так как назначен конкретный пользователь
        task.save()

        # Уведомляем нового исполнителя
        try:
            notification_text = f"📋 **Вам назначена задача**\n\n{format_task_info(task)}"
            markup = get_task_actions_markup(task.id, task.status, task.report_attachments, False, True)
            safe_edit_or_send_message(new_assignee.telegram_id, notification_text, reply_markup=markup, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Failed to notify new assignee {new_assignee.telegram_id}: {e}")

        from bot.handlers.utils import clear_user_state
        clear_user_state(chat_id)

        text = f"➡️ Исполнитель задачи '{task.title}' изменен с {old_assignee.user_name} на {new_assignee.user_name}"
        safe_edit_or_send_message(call.message.chat.id, text, reply_markup=TASK_MANAGEMENT_MARKUP, message_id=call.message.message_id)

    except (ValueError, ObjectDoesNotExist):
        bot.answer_callback_query(call.id, "Ошибка при смене исполнителя", show_alert=True)


def edit_due_date_callback(call: CallbackQuery) -> None:
    try:
        task_id = int(call.data.split('_')[2])
        task = Task.objects.get(id=task_id)
        chat_id = get_chat_id_from_update(call)
        allowed, error_msg = check_permissions(chat_id, task, require_creator=False)
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
        allowed, error_msg = check_permissions(chat_id, task, require_creator=False)
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
        allowed, error_msg = check_permissions(chat_id, task, require_creator=False)
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

        text = f"➡️ Задача '{task.title}' снова стала активной и доступной для редактирования"
        safe_edit_or_send_message(call.message.chat.id, text, reply_markup=TASK_MANAGEMENT_MARKUP, message_id=call.message.message_id)

        # Уведомляем всех исполнителей, если инициатор не единственный исполнитель
        assignees = task.get_assignees()
        for assignee in assignees:
            if assignee.telegram_id != chat_id:
                try:
                    bot.send_message(
                        assignee.telegram_id,
                        f"🔄 Задача снова активна\n\n{format_task_info(task)}\n\nЗадача была возобновлена."
                    )
                except Exception as e:
                    logger.error(f"Не удалось уведомить исполнителя {assignee.user_name} задачи {task_id}: {e}")

        # Подтверждаем callback
        bot.answer_callback_query(call.id)

    except (ValueError, ObjectDoesNotExist) as e:
        logger.error(f"Error in reopen_task_callback: {e}")
        bot.answer_callback_query(call.id, "Задача не найдена", show_alert=True)
    except Exception as e:
        logger.error(f"Unexpected error in reopen_task_callback: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка", show_alert=True)