import os
import json
from datetime import datetime, timedelta
from django.utils import timezone
from bot import bot, logger
from bot.models import User, Task, Subtask, UserState
from telebot.apihelper import ApiTelegramException
from bot.keyboards import (
    get_task_actions_markup, get_task_confirmation_markup,
    get_subtask_toggle_markup, get_tasks_list_markup, get_user_selection_markup,
    TASK_MANAGEMENT_MARKUP, UNIVERSAL_BUTTONS, main_markup
)
from telebot.types import (
    Message,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery,
)
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction


def safe_edit_or_send_message(chat_id: str, text: str, reply_markup=None, message_id=None) -> None:
    """Безопасно редактирует сообщение или отправляет новое при ошибке"""
    try:
        if message_id:
            bot.edit_message_text(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                message_id=message_id
            )
        else:
            bot.send_message(chat_id, text, reply_markup=reply_markup)
    except ApiTelegramException as e:
        logger.warning(f"Failed to edit message {message_id} in chat {chat_id}: {e}")
        try:
            bot.send_message(chat_id, text, reply_markup=reply_markup)
        except Exception as send_e:
            logger.error(f"Failed to send message to chat {chat_id}: {send_e}")


def get_user_state(chat_id) -> dict:
    try:
        user_state = UserState.objects.get(user__telegram_id=chat_id)
        # Возвращаем словарь с полями state и data
        result = {
            'state': user_state.state or '',  # state всегда из поля модели
        }
        # Если data - это строка JSON, парсим её, иначе используем как есть
        if isinstance(user_state.data, str):
            try:
                data_dict = json.loads(user_state.data)
                # Обновляем result данными из data, но state не перезаписываем
                for key, value in data_dict.items():
                    if key != 'state':  # Не перезаписываем state из data
                        result[key] = value
            except (json.JSONDecodeError, TypeError):
                if user_state.data:
                    result['data'] = user_state.data
        elif isinstance(user_state.data, dict):
            # Обновляем result данными из data, но state не перезаписываем
            for key, value in user_state.data.items():
                if key != 'state':  # Не перезаписываем state из data
                    result[key] = value
        else:
            if user_state.data:
                result['data'] = user_state.data
        return result
    except UserState.DoesNotExist:
        return {}
    except Exception as e:
        logger.error(f"Ошибка при получении состояния пользователя {chat_id}: {e}")
        return {}


def set_user_state(chat_id, state_data: dict) -> None:
    # Создаем копию, чтобы не изменять исходный словарь
    state_data_copy = state_data.copy() if state_data else {}
    
    # Извлекаем state из словаря, остальное идет в data
    current_state = state_data_copy.pop('state', None)
    if current_state is None:
        # Если state не указан, пытаемся получить текущий
        try:
            existing = UserState.objects.get(user__telegram_id=chat_id)
            current_state = existing.state
        except UserState.DoesNotExist:
            current_state = ''
    
    # Остальные данные сохраняем в data
    data_to_save = state_data_copy
    
    user = get_or_create_user(chat_id)
    UserState.objects.update_or_create(
        user=user,
        defaults={
            'state': current_state,
            'data': data_to_save
        }
    )


def clear_user_state(chat_id) -> None:
    UserState.objects.filter(user__telegram_id=chat_id).delete()


def get_or_create_user(telegram_id: str, telegram_username: str = None, first_name: str = None) -> User:
    user, created = User.objects.get_or_create(
        telegram_id=telegram_id,
        defaults={
            'user_name': telegram_username or f"user_{telegram_id}",
            'first_name': first_name or "",
            'is_admin': False
        }
    )
    if not created and (telegram_username or first_name):
        update_fields = {}
        if telegram_username and user.user_name != telegram_username:
            update_fields['user_name'] = telegram_username
        if first_name and user.first_name != first_name:
            update_fields['first_name'] = first_name
        if update_fields:
            User.objects.filter(telegram_id=telegram_id).update(**update_fields)
            user.refresh_from_db()
    return user


def check_permissions(user_id: str, task: Task = None, require_creator: bool = False) -> tuple[bool, str]:
    user = get_or_create_user(user_id)
    if user.is_admin:
        return True, ""
    if task is None:
        return True, ""
    if require_creator:
        if str(task.creator.telegram_id) != str(user_id):
            return False, "❌ У вас нет прав для этого действия"
    else:
        if str(task.creator.telegram_id) != str(user_id) and str(task.assignee.telegram_id) != str(user_id):
            return False, "❌ У вас нет доступа к этой задаче"
    return True, ""


def format_task_info(task: Task, show_details: bool = False) -> str:
    status_text = {
        'active': '🔄 Активная',
        'pending_review': '⏳ Ожидает подтверждения',
        'completed': '✅ Завершена',
        'cancelled': '❌ Отменена'
    }.get(task.status, '❓ Неизвестный статус')

    text = f"📋 ЗАДАЧА #{task.id}\n\n"
    text += f"📝 Название: {task.title}\n"
    text += f"📊 Статус: {status_text}\n"
    text += f"👤 Создатель: {task.creator.user_name}\n"
    text += f"👨‍💼 Исполнитель: {task.assignee.user_name}\n"

    if task.description:
        text += f"📖 Описание: {task.description}\n"

    if task.due_date:
        text += f"⏰ Срок: {task.due_date.strftime('%d.%m.%Y %H:%M')}\n"

    if task.status == 'completed' and task.closed_at:
        text += f"✅ Завершена: {task.closed_at.strftime('%d.%m.%Y %H:%M')}\n"

    if task.status == 'pending_review' and task.report_text:
        text += f"\n📄 ОТЧЕТ:\n{task.report_text}\n"

    return text


def get_chat_id_from_update(update) -> str:
    if hasattr(update, 'message') and update.message:
        return str(update.message.chat.id)
    elif hasattr(update, 'callback_query') and update.callback_query:
        return str(update.callback_query.message.chat.id)
    return ""


def parse_datetime_from_state(date_value):
    """
    Парсит дату/время из состояния пользователя (может быть datetime или строка ISO)
    """
    if date_value is None:
        return None
    if isinstance(date_value, datetime):
        return date_value
    if isinstance(date_value, str):
        try:
            # Пробуем разные форматы
            for fmt in ['%Y-%m-%dT%H:%M:%S.%f%z', '%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%d %H:%M:%S%z', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d']:
                try:
                    dt = datetime.strptime(date_value, fmt)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.get_current_timezone())
                    return dt
                except ValueError:
                    continue
            # Если ничего не подошло, пробуем fromisoformat
            return datetime.fromisoformat(date_value.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            logger.error(f"Не удалось распарсить дату: {date_value}")
            return None
    return date_value


def show_task_progress(chat_id: str, task: Task, is_creator: bool = False, is_assignee: bool = False, message_id: int = None) -> None:
    text = format_task_info(task, show_details=True)
    subtasks = task.subtasks.all()
    if subtasks:
        text += "\n\n📋 ПОДЗАДАЧИ:"
        for subtask in subtasks:
            status = "✅" if subtask.is_completed else "⏳"
            completed_date = f" ({subtask.completed_at.strftime('%d.%m.%Y')})" if subtask.completed_at else ""
            text += f"\n{status} {subtask.title}{completed_date}"
    markup = get_task_actions_markup(task.id, task.status, task.report_attachments, is_creator, is_assignee)
    safe_edit_or_send_message(chat_id, text, reply_markup=markup, message_id=message_id)
