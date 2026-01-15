from datetime import datetime, timedelta
from django.utils import timezone
from bot import bot, logger
from bot.models import User, Task, Subtask, UserState
from bot.keyboards import (
    get_task_actions_markup, get_task_confirmation_markup,
    get_subtask_toggle_markup, get_tasks_list_markup, get_user_selection_markup,
    TASK_MANAGEMENT_MARKUP, UNIVERSAL_BUTTONS, main_markup
)
from bot.handlers.utils import (
    get_or_create_user, get_chat_id_from_update, safe_edit_or_send_message, get_user_state,
    set_user_state, clear_user_state, check_permissions, format_task_info, show_task_progress
)
from telebot.types import (
    Message,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery,
)
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction

# Обработчик /start перенесен в commands.py для избежания дублирования

def create_task_command(message: Message) -> None:
    create_task_command_logic(message)

def create_task_callback(call: CallbackQuery) -> None:
    create_task_command_logic(call)
def tasks_command_logic(update) -> None:
    chat_id = get_chat_id_from_update(update)
    user = get_or_create_user(chat_id)
    active_tasks = Task.objects.filter(
        assignee=user,
        status__in=['active', 'pending_review']
    ).order_by('due_date', '-created_at')
    if not active_tasks:
        text = "📋 У вас нет активных задач"
        bot.send_message(chat_id, text, reply_markup=TASK_MANAGEMENT_MARKUP)
        return
    text = f"📋 ВАШИ АКТИВНЫЕ ЗАДАЧИ\n\n"
    markup = get_tasks_list_markup(active_tasks, is_creator_view=False)
    bot.send_message(chat_id, text, reply_markup=markup)
@bot.message_handler(commands=["my_created_tasks"])
def my_created_tasks_command(message: Message) -> None:
    my_created_tasks_command_logic(message)
@bot.callback_query_handler(func=lambda c: c.data == "my_created_tasks")
def my_created_tasks_callback(call: CallbackQuery) -> None:
    chat_id = get_chat_id_from_update(call)
    user = get_or_create_user(chat_id)
    created_tasks = Task.objects.filter(creator=user).order_by('-created_at')
    if not created_tasks:
        safe_edit_or_send_message(
            chat_id=call.message.chat.id,
            text="📋 Вы еще не создали ни одной задачи",
            reply_markup=TASK_MANAGEMENT_MARKUP,
            message_id=call.message.message_id
        )
        return
    text = f"📋 ЗАДАЧИ, СОЗДАННЫЕ ВАМИ\n\n"
    markup = get_tasks_list_markup(created_tasks, is_creator_view=True)
    safe_edit_or_send_message(
        chat_id=call.message.chat.id,
        text=text,
        reply_markup=markup,
        message_id=call.message.message_id
    )
def my_created_tasks_command_logic(update) -> None:
    chat_id = get_chat_id_from_update(update)
    user = get_or_create_user(chat_id)
    created_tasks = Task.objects.filter(creator=user).order_by('-created_at')
    if not created_tasks:
        text = "📋 Вы еще не создали ни одной задачи"
        bot.send_message(chat_id, text, reply_markup=TASK_MANAGEMENT_MARKUP)
        return
    text = f"📋 ЗАДАЧИ, СОЗДАННЫЕ ВАМИ\n\n"
    markup = get_tasks_list_markup(created_tasks, is_creator_view=True)
    bot.send_message(chat_id, text, reply_markup=markup)
def create_task_command_logic(update) -> None:
    chat_id = get_chat_id_from_update(update)
    logger.info(f"Начало создания задачи для пользователя {chat_id}")
    user = get_or_create_user(chat_id)
    text = "📝 СОЗДАНИЕ НОВОЙ ЗАДАЧИ\n\n🎯 Введите название задачи:"
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("⬅️ Отмена", callback_data="main_menu"))
    bot.send_message(chat_id, text, reply_markup=markup)
    set_user_state(chat_id, {'state': 'waiting_task_title'})
    logger.info(f"Установлено состояние 'waiting_task_title' для пользователя {chat_id}")

# Обработчик close_task перенесен в commands.py
# Обработчик task_progress перенесен в commands.py
# Обработчик debug перенесен в commands.py

def initiate_task_close(chat_id: str, task: Task) -> None:
    if task.status not in ['active', 'pending_review']:
        bot.send_message(chat_id, f"❌ Невозможно закрыть задачу в статусе '{task.get_status_display()}'")
        return
    if task.creator.telegram_id == task.assignee.telegram_id:
        task.status = 'completed'
        task.closed_at = timezone.now()
        task.save()
        try:
            from bot.schedulers import unschedule_task_reminder
            unschedule_task_reminder(task.id)
        except Exception as e:
            print(f"Warning: Failed to unschedule reminder for task {task.id}: {e}")
        text = f"✅ ЗАДАЧА ЗАКРЫТА\n\n{format_task_info(task)}\n\nЗадача успешно закрыта!"
        bot.send_message(chat_id, text, reply_markup=TASK_MANAGEMENT_MARKUP)
    else:
        text = f"""📄 ОТПРАВКА ОТЧЕТА О ВЫПОЛНЕНИИ
{format_task_info(task)}
📝 Отправьте текст отчета о выполнении задачи.
Отчет должен содержать минимум 10 символов.
💡 Вы можете прикрепить фото или файлы к сообщению с отчетом.
Отправьте текст отчета с вложениями (если нужно) в одном сообщении."""
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("⬅️ Отмена", callback_data="tasks_back"))
        bot.send_message(chat_id, text, reply_markup=markup)
        set_user_state(chat_id, {
            'state': 'waiting_task_report',
            'task_id': task.id
        })
def handle_task_report(message: Message) -> None:
    user_state = get_user_state(str(message.chat.id))
    if not user_state or user_state.get('state') != 'waiting_task_report':
        return
    task_id = user_state['task_id']
    try:
        task = Task.objects.get(id=task_id)
        if str(message.chat.id) != task.assignee.telegram_id:
            bot.send_message(message.chat.id, "❌ У вас нет прав отправлять отчет по этой задаче")
            return
        if task.status != 'active':
            bot.send_message(message.chat.id, f"❌ Невозможно отправить отчет. Задача находится в статусе '{task.get_status_display()}'")
            return
        user = get_or_create_user(str(message.chat.id))
        attachments = []
        if message.photo:
            file_id = message.photo[-1].file_id
            attachments.append({
                'file_id': file_id,
                'type': 'photo',
                'file_name': None
            })
        elif message.document:
            file_id = message.document.file_id
            file_name = getattr(message.document, 'file_name', None)
            attachments.append({
                'file_id': file_id,
                'type': 'document',
                'file_name': file_name
            })
        report_text = message.text.strip() if message.text else ""
        if len(report_text) < 10 and not attachments:
            bot.send_message(message.chat.id, "❌ Отчет должен содержать минимум 10 символов текста ИЛИ вложения (фото/файлы)")
            return
        elif len(report_text) < 10 and attachments:
            report_text = f"Отчет с вложениями ({len(attachments)} файлов)"
        task.report_text = report_text
        task.report_attachments = attachments
        task.status = 'pending_review'
        task.save()
        attachments_info = ""
        if task.report_attachments:
            attachments_info = f"\n📎 Вложений в отчете: {len(task.report_attachments)}"
        creator_text = f"""📄 ПОЛУЧЕН ОТЧЕТ О ВЫПОЛНЕНИИ
{format_task_info(task)}
👤 Исполнитель: {task.assignee.user_name}
📝 Отчет: {task.report_text}{attachments_info}
"""
        markup = get_task_confirmation_markup(task.id)
        try:
            bot.send_message(task.creator.telegram_id, creator_text, reply_markup=markup)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Не удалось уведомить создателя: {e}")
        bot.send_message(message.chat.id, "✅ Отчет успешно отправлен создателю для проверки", reply_markup=TASK_MANAGEMENT_MARKUP)
    except Task.DoesNotExist:
        bot.send_message(message.chat.id, "❌ Задача не найдена")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка при отправке отчета: {e}")
    finally:
        clear_user_state(str(message.chat.id))
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
# Обработчик tasks_back перенесен в main.py
    tasks_command(call)
# Обработчик back_to_assignee_type перенесен в task_creation.py
    back_to_assignee_selection_callback(call)
# Обработчик view_report_attachments перенесен в reports.py
    try:
        task_id = int(call.data.split('_')[3])
        task = Task.objects.get(id=task_id)
        chat_id = get_chat_id_from_update(call)
        allowed, error_msg = check_permissions(chat_id, task, require_creator=False)
        if not allowed:
            bot.answer_callback_query(call.id, error_msg, show_alert=True)
            return
        if not task.report_attachments:
            bot.answer_callback_query(call.id, "У этой задачи нет вложений в отчете", show_alert=True)
            return
        text = ""
        for i, attachment in enumerate(task.report_attachments, 1):
            attachment_type = attachment.get('type', 'unknown')
            file_name = attachment.get('file_name', f'Вложение {i}')
            text += f"\n{i}. {attachment_type.upper()}: {file_name}"
        text += "\n\n💡 Вложения доступны в оригинальном сообщении с отчетом."
        bot.edit_message_text(chat_id=call.message.chat.id, text=text, message_id=call.message.message_id)
    except (ValueError, ObjectDoesNotExist):
        bot.answer_callback_query(call.id, "Задача не найдена", show_alert=True)
# Обработчик main_menu перенесен в main.py
    text = "🏠 Главное меню"
    safe_edit_or_send_message(call.message.chat.id, text, reply_markup=TASK_MANAGEMENT_MARKUP, message_id=call.message.message_id)
