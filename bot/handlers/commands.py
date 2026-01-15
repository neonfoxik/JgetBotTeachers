from bot.handlers.utils import (
    get_or_create_user, get_chat_id_from_update, safe_edit_or_send_message, format_task_info
)
from bot import bot, logger
from bot.models import User, Task
from bot.keyboards import get_tasks_list_markup, TASK_MANAGEMENT_MARKUP, main_markup
from telebot.types import Message, CallbackQuery
from django.core.exceptions import ObjectDoesNotExist


# Декоратор удален - обработчик регистрируется в views.py через register_handlers()
def start_command(message: Message) -> None:
    try:
        chat_id = str(message.chat.id)
        logger.info(f"Обработчик /start вызван для пользователя {chat_id}")
        
        user = get_or_create_user(
            telegram_id=chat_id,
            telegram_username=message.from_user.username,
            first_name=message.from_user.first_name
        )
        logger.info(f"Пользователь получен/создан: {user.user_name}")

        welcome_text = f"""👋 Привет, {user.first_name or user.user_name}!

🤖 Я бот для управления задачами. Выберите действие:"""

        bot.send_message(chat_id, welcome_text, reply_markup=main_markup)
        logger.info(f"Приветственное сообщение отправлено пользователю {chat_id}")
    except Exception as e:
        logger.error(f"Ошибка в обработчике /start: {e}")
        import traceback
        logger.error(traceback.format_exc())
        try:
            # Используем chat_id если он определен, иначе message.chat.id
            error_chat_id = chat_id if 'chat_id' in locals() else str(message.chat.id)
            bot.send_message(error_chat_id, "❌ Произошла ошибка. Попробуйте позже.")
        except:
            pass


def tasks_command(message: Message) -> None:
    tasks_command_logic(message)


def tasks_callback(call: CallbackQuery) -> None:
    # Проверяем, находится ли пользователь уже в разделе "мои задачи" (активные задачи)
    current_text = getattr(call.message, 'text', '') or getattr(call.message, 'caption', '') or ''
    if "ВАШИ АКТИВНЫЕ ЗАДАЧИ" in current_text:
        # Показываем уведомление, что пользователь уже в этом разделе
        bot.answer_callback_query(
            call.id,
            "ℹ️ Вы уже находитесь в разделе 'Мои задачи'",
            show_alert=False
        )
        return

    # Вызываем логику напрямую с передачей callback объекта
    tasks_command_logic(call)


def tasks_command_logic(update) -> None:
    chat_id = get_chat_id_from_update(update)
    user = get_or_create_user(chat_id)

    # Получаем активные задачи пользователя
    active_tasks = Task.objects.filter(
        assignee=user,
        status__in=['active', 'pending_review']
    ).order_by('-created_at')

    if not active_tasks:
        text = "📋 У вас нет активных задач"
        markup = TASK_MANAGEMENT_MARKUP
    else:
        text = f"📋 ВАШИ АКТИВНЫЕ ЗАДАЧИ\n\n"
        markup = get_tasks_list_markup(active_tasks, is_creator_view=False)

    # Если это callback (есть message в update), редактируем сообщение
    if hasattr(update, 'message') and hasattr(update.message, 'message_id'):
        bot.edit_message_text(
            chat_id=chat_id,
            text=text,
            reply_markup=markup,
            message_id=update.message.message_id
        )
    else:
        safe_edit_or_send_message(chat_id, text, reply_markup=markup, message_id=update.message.message_id)

def my_created_tasks_command(message: Message) -> None:
    my_created_tasks_command_logic(message)


def my_created_tasks_callback(call: CallbackQuery) -> None:
    # Проверяем, находится ли пользователь уже в разделе "мои задачи"
    current_text = getattr(call.message, 'text', '') or getattr(call.message, 'caption', '') or ''
    if "ЗАДАЧИ, СОЗДАННЫЕ ВАМИ" in current_text:
        # Показываем уведомление, что пользователь уже в этом разделе
        bot.answer_callback_query(
            call.id,
            "ℹ️ Вы уже находитесь в разделе 'Мои задачи'",
            show_alert=False
        )
        return

    # Вызываем логику напрямую с передачей callback объекта
    my_created_tasks_command_logic(call)


def my_created_tasks_command_logic(update) -> None:
    chat_id = get_chat_id_from_update(update)
    user = get_or_create_user(chat_id)

    # Получаем задачи созданные пользователем
    created_tasks = Task.objects.filter(creator=user).order_by('-created_at')

    if not created_tasks:
        text = "📋 Вы еще не создали ни одной задачи"
        markup = TASK_MANAGEMENT_MARKUP
    else:
        text = f"📋 ЗАДАЧИ, СОЗДАННЫЕ ВАМИ\n\n"
        markup = get_tasks_list_markup(created_tasks, is_creator_view=True)

    # Если это callback (есть message в update), редактируем сообщение
    if hasattr(update, 'message') and hasattr(update.message, 'message_id'):
        bot.edit_message_text(
            chat_id=chat_id,
            text=text,
            reply_markup=markup,
            message_id=update.message.message_id
        )
    else:
        # Если это команда, отправляем новое сообщение
        bot.send_message(chat_id, text, reply_markup=markup)


# Обработчик create_task перенесен в tasks.py для избежания дублирования


def close_task_command(message: Message) -> None:
    try:
        parts = message.text.split()
        if len(parts) != 2:
            bot.send_message(message.chat.id, "❌ Использование: /close_task <ID задачи>")
            return

        task_id = int(parts[1])
        task = Task.objects.get(id=task_id)
        chat_id = str(message.chat.id)
        user = get_or_create_user(chat_id)

        if task.assignee != user:
            bot.send_message(message.chat.id, "❌ Вы не являетесь исполнителем этой задачи")
            return

        if task.status != 'active':
            bot.send_message(message.chat.id, f"❌ Невозможно закрыть задачу в статусе '{task.get_status_display()}'")
            return

        # Инициируем процесс закрытия задачи
        initiate_task_close(chat_id, task)

    except (ValueError, ObjectDoesNotExist):
        bot.send_message(message.chat.id, "❌ Задача не найдена")


def task_progress_command(message: Message) -> None:
    try:
        parts = message.text.split()
        if len(parts) != 2:
            bot.send_message(message.chat.id, "❌ Использование: /task_progress <ID задачи>")
            return

        task_id = int(parts[1])
        task = Task.objects.get(id=task_id)
        chat_id = str(message.chat.id)
        user = get_or_create_user(chat_id)

        allowed, error_msg = check_permissions(chat_id, task, require_creator=False)
        if not allowed:
            bot.send_message(message.chat.id, error_msg)
            return

        is_creator = task.creator.telegram_id == user.telegram_id
        is_assignee = task.assignee.telegram_id == user.telegram_id
        show_task_progress(chat_id, task, is_creator, is_assignee)

    except (ValueError, ObjectDoesNotExist):
        bot.send_message(message.chat.id, "❌ Задача не найдена")


def debug_command(message: Message) -> None:
    chat_id = str(message.chat.id)
    user = get_or_create_user(chat_id)

    debug_info = f"""
🐛 DEBUG ИНФОРМАЦИЯ

👤 Пользователь: {user.user_name}
🆔 Telegram ID: {user.telegram_id}
👑 Админ: {'Да' if user.is_admin else 'Нет'}
📅 Дата регистрации: {user.created_at.strftime('%d.%m.%Y %H:%M')}

📊 СТАТИСТИКА ЗАДАЧ:
"""

    # Статистика задач
    total_created = Task.objects.filter(creator=user).count()
    total_assigned = Task.objects.filter(assignee=user).count()
    active_tasks = Task.objects.filter(assignee=user, status='active').count()
    completed_tasks = Task.objects.filter(assignee=user, status='completed').count()

    debug_info += f"""
📝 Создано задач: {total_created}
📋 Назначено задач: {total_assigned}
🔄 Активных задач: {active_tasks}
✅ Завершенных задач: {completed_tasks}
"""

    bot.send_message(chat_id, debug_info)
