import os
import json
from datetime import datetime, timedelta
from django.utils import timezone
from bot import bot
from bot.models import User, Task, Subtask, UserState
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
def get_user_state(chat_id) -> dict:
    try:
        user = get_or_create_user(str(chat_id))
        user_state = UserState.objects.get(user=user)
        data = {}
        for k, v in user_state.data.items():
            if k == 'due_date' and v and isinstance(v, str):
                try:
                    from datetime import datetime
                    from django.utils import timezone
                    dt = datetime.strptime(v, '%Y-%m-%d %H:%M:%S')
                    data[k] = dt.replace(tzinfo=timezone.get_current_timezone())
                except (ValueError, TypeError):
                    data[k] = None
            else:
                data[k] = v
        return {
            'state': user_state.state,
            **data
        }
    except UserState.DoesNotExist:
        return {}
def set_user_state(chat_id, state_data: dict) -> None:
    user = get_or_create_user(str(chat_id))
    state = state_data.get('state', '')
    data = {}
    for k, v in state_data.items():
        if k != 'state':
            if k == 'due_date' and v and hasattr(v, 'strftime'):
                data[k] = v.strftime('%Y-%m-%d %H:%M:%S')
            else:
                data[k] = v
    UserState.objects.update_or_create(
        user=user,
        defaults={
            'state': state,
            'data': data
        }
    )
def clear_user_state(chat_id) -> None:
    try:
        user = get_or_create_user(str(chat_id))
        UserState.objects.filter(user=user).delete()
    except UserState.DoesNotExist:
        pass
def get_or_create_user(telegram_id: str, telegram_username: str = None, first_name: str = None) -> User:
    user, created = User.objects.get_or_create(
        telegram_id=telegram_id,
        defaults={
            'user_name': first_name or telegram_username or f'User_{telegram_id}',
            'is_admin': False,  
            'timezone': 'UTC'
        }
    )
    if not created and (first_name or telegram_username) and user.user_name != (first_name or telegram_username):
        user.user_name = first_name or telegram_username
        user.save()
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
    text = f"""📋 ЗАДАЧА #{task.id}
🎯 Название: {task.title}
📊 Статус: {status_text}
👤 Создатель: {task.creator.user_name}
🎯 Исполнитель: {task.assignee.user_name}
📅 Создано: {task.created_at.strftime('%d.%m.%Y %H:%M')}"""
    if task.description:
        text += f"\n📝 Описание: {task.description}"
    if task.due_date:
        text += f"\n⏰ Срок: {task.due_date.strftime('%d.%m.%Y %H:%M')}"
        if task.due_date < timezone.now() and task.status == 'active':
            text += " 🚨 ПРОСРОЧЕНА!"
    if task.progress:
        percentage = task.get_progress_percentage()
        text += f"\n📊 Прогресс: {task.progress} ({percentage}%)"
    if show_details and task.report_text:
        text += f"\n📄 Отчет: {task.report_text}"
    if task.attachments:
        text += f"\n📎 Вложений: {len(task.attachments)}"
    if show_details and task.report_attachments:
        text += f"\n📎 Вложений в отчете: {len(task.report_attachments)}"
    text += "\n\n"
    return text
@bot.message_handler(commands=["start"])
def start_command(message: Message) -> None:
    user = get_or_create_user(
        telegram_id=str(message.chat.id),
        telegram_username=message.from_user.username,
        first_name=message.from_user.first_name
    )
    welcome_text = f"👋 Добро пожаловать, {user.user_name}!\n\nЯ бот для управления задачами. Выберите действие:"
    bot.send_message(message.chat.id, welcome_text, reply_markup=main_markup)
def get_chat_id_from_update(update) -> str:
    if hasattr(update, 'chat'):
        return str(update.chat.id)
    elif hasattr(update, 'message') and hasattr(update.message, 'chat'):
        return str(update.message.chat.id)
    else:
        raise ValueError("Cannot extract chat_id from update")
@bot.message_handler(commands=["tasks"])
def tasks_command(message: Message) -> None:
    tasks_command_logic(message)
@bot.callback_query_handler(func=lambda c: c.data == "tasks")
def tasks_callback(call: CallbackQuery) -> None:
    tasks_command_logic(call)
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
    my_created_tasks_command_logic(call)
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
@bot.message_handler(commands=["create_task"])
def create_task_command(message: Message) -> None:
    create_task_command_logic(message)
@bot.callback_query_handler(func=lambda c: c.data == "create_task")
def create_task_callback(call: CallbackQuery) -> None:
    create_task_command_logic(call)
def create_task_command_logic(update) -> None:
    chat_id = get_chat_id_from_update(update)
    user = get_or_create_user(chat_id)
    text = "📝 СОЗДАНИЕ НОВОЙ ЗАДАЧИ\n\n🎯 Введите название задачи:"
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("⬅️ Отмена", callback_data="main_menu"))
    bot.send_message(chat_id, text, reply_markup=markup)
    set_user_state(chat_id, {'state': 'waiting_task_title'})
@bot.message_handler(commands=["close_task"])
def close_task_command(message: Message) -> None:
    args = message.text.split()
    if len(args) < 2:
        bot.send_message(message.chat.id, "❌ Использование: /close_task <ID задачи>")
        return
    try:
        task_id = int(args[1])
    except ValueError:
        bot.send_message(message.chat.id, "❌ ID задачи должен быть числом")
        return
    try:
        task = Task.objects.get(id=task_id)
    except Task.DoesNotExist:
        bot.send_message(message.chat.id, "❌ Задача не найдена")
        return
    allowed, error_msg = check_permissions(message.chat.id, task, require_creator=False)
    if not allowed:
        bot.send_message(message.chat.id, error_msg)
        return
    initiate_task_close(message.chat.id, task)
@bot.message_handler(commands=["task_progress"])
def task_progress_command(message: Message) -> None:
    args = message.text.split()
    if len(args) < 2:
        bot.send_message(message.chat.id, "❌ Использование: /task_progress <ID задачи>")
        return
    try:
        task_id = int(args[1])
    except ValueError:
        bot.send_message(message.chat.id, "❌ ID задачи должен быть числом")
        return
    try:
        task = Task.objects.get(id=task_id)
    except Task.DoesNotExist:
        bot.send_message(message.chat.id, "❌ Задача не найдена")
        return
    chat_id = str(message.chat.id)
    allowed, error_msg = check_permissions(chat_id, task, require_creator=False)
    if not allowed:
        bot.send_message(chat_id, error_msg)
        return
    user = get_or_create_user(chat_id)
    is_creator = task.creator.telegram_id == user.telegram_id
    is_assignee = task.assignee.telegram_id == user.telegram_id
    show_task_progress(chat_id, task, is_creator, is_assignee)
@bot.message_handler(commands=["debug"])
def debug_command(message: Message) -> None:
    user = get_or_create_user(str(message.chat.id))
    state_info = "Нет активного состояния"
    if hasattr(bot, 'user_states') and message.chat.id in bot.user_states:
        state_info = f"Состояние: {bot.user_states[message.chat.id]}"
    text = f"""🐛 ОТЛАДОЧНАЯ ИНФОРМАЦИЯ
👤 Пользователь: {user.user_name} ({user.telegram_id})
🔧 {state_info}
📊 Статистика:
• Активных задач: {Task.objects.filter(assignee=user, status='active').count()}
• Созданных задач: {Task.objects.filter(creator=user).count()}"""
    bot.send_message(message.chat.id, text)
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
@bot.message_handler(content_types=['text', 'photo', 'document'],
                    func=lambda message: not (message.text and message.text.startswith('/')))
def handle_task_report(message: Message) -> None:
    if message.text and message.text.startswith('/'):
        return  
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
def show_task_progress(chat_id: str, task: Task, is_creator: bool = False, is_assignee: bool = False) -> None:
    text = format_task_info(task, show_details=True)
    subtasks = task.subtasks.all()
    if subtasks:
        text += "\n\n📋 ПОДЗАДАЧИ:"
        for subtask in subtasks:
            status = "✅" if subtask.is_completed else "⏳"
            completed_date = f" ({subtask.completed_at.strftime('%d.%m.%Y')})" if subtask.completed_at else ""
            text += f"\n{status} {subtask.title}{completed_date}"
    markup = get_task_actions_markup(task.id, task.status, task.report_attachments, is_creator, is_assignee)
    bot.send_message(chat_id, text, reply_markup=markup)
@bot.message_handler(func=lambda message: not message.text.startswith('/') and not message.text.startswith('@'))
def handle_task_creation_messages(message: Message) -> None:
    user_state = get_user_state(str(message.chat.id))
    if not user_state:
        return  
    state = user_state.get('state')
    if state == 'waiting_task_title':
        if len(message.text.strip()) < 3:
            bot.send_message(message.chat.id, "❌ Название задачи должно содержать минимум 3 символа")
            return
        user_state['title'] = message.text.strip()
        user_state['state'] = 'waiting_task_description'
        set_user_state(str(message.chat.id), user_state)
        text = "📝 Теперь введите описание задачи (или 'пропустить' для пустого описания):"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Пропустить описание", callback_data="skip_description"))
        markup.add(InlineKeyboardButton("⬅️ Отмена", callback_data="cancel_task_creation"))
        bot.send_message(message.chat.id, text, reply_markup=markup)
    elif state == 'waiting_task_description':
        user_state['description'] = None if message.text.lower() in ['пусто', 'skip', 'пропустить'] else message.text.strip()
        user_state['state'] = 'waiting_due_date'
        set_user_state(str(message.chat.id), user_state)
        description_text = user_state['description'] or "не указано"
        text = f"📅 Введите срок выполнения задачи в формате ДД.ММ.ГГГГ ЧЧ:ММ\n\nТекущее описание: {description_text}"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Без срока", callback_data="skip_due_date"))
        markup.add(InlineKeyboardButton("⬅️ Отмена", callback_data="cancel_task_creation"))
        bot.send_message(message.chat.id, text, reply_markup=markup)
    elif state == 'waiting_due_date':
        if message.text.lower() in ['пусто', 'skip', 'нет', 'пропустить']:
            user_state['due_date'] = None
        else:
            try:
                due_date = datetime.strptime(message.text.strip(), '%d.%m.%Y %H:%M')
                user_state['due_date'] = due_date.replace(tzinfo=timezone.get_current_timezone())
            except ValueError:
                bot.send_message(message.chat.id, "❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ ЧЧ:ММ")
                return
        user_state['state'] = 'waiting_assignee_selection'
        set_user_state(str(message.chat.id), user_state)
        show_assignee_selection_menu(str(message.chat.id), user_state)
    elif state == 'editing_task_title':
        if len(message.text.strip()) < 3:
            bot.send_message(message.chat.id, "❌ Название задачи должно содержать минимум 3 символа")
            return
        try:
            task_id = user_state['task_id']
            task = Task.objects.get(id=task_id)
            chat_id_str = str(message.chat.id)
            allowed, error_msg = check_permissions(chat_id_str, task, require_creator=True)
            if not allowed:
                bot.send_message(message.chat.id, error_msg)
                return
            old_title = task.title
            task.title = message.text.strip()
            task.save()
            text = ""
            bot.send_message(message.chat.id, text, reply_markup=TASK_MANAGEMENT_MARKUP)
        except Task.DoesNotExist:
            bot.send_message(message.chat.id, "❌ Задача не найдена")
        finally:
            clear_user_state(str(message.chat.id))
    elif state == 'editing_task_description':
        try:
            task_id = user_state['task_id']
            task = Task.objects.get(id=task_id)
            chat_id_str = str(message.chat.id)
            allowed, error_msg = check_permissions(chat_id_str, task, require_creator=True)
            if not allowed:
                bot.send_message(message.chat.id, error_msg)
                return
            old_description = task.description or "не указано"
            task.description = None if message.text.lower() in ['пусто', 'skip', 'пропустить'] else message.text.strip()
            task.save()
            new_description = task.description or "не указано"
            text = ""
            bot.send_message(message.chat.id, text, reply_markup=TASK_MANAGEMENT_MARKUP)
        except Task.DoesNotExist:
            bot.send_message(message.chat.id, "❌ Задача не найдена")
        finally:
            clear_user_state(str(message.chat.id))
    elif state == 'editing_task_due_date':
        try:
            task_id = user_state['task_id']
            task = Task.objects.get(id=task_id)
            chat_id_str = str(message.chat.id)
            allowed, error_msg = check_permissions(chat_id_str, task, require_creator=True)
            if not allowed:
                bot.send_message(message.chat.id, error_msg)
                return
            if message.text.lower() in ['пусто', 'skip', 'нет', 'пропустить']:
                old_due = task.due_date.strftime('%d.%m.%Y %H:%M') if task.due_date else "не указан"
                task.due_date = None
                new_due = "не указан"
            else:
                try:
                    due_date = datetime.strptime(message.text.strip(), '%d.%m.%Y %H:%M')
                    old_due = task.due_date.strftime('%d.%m.%Y %H:%M') if task.due_date else "не указан"
                    task.due_date = due_date.replace(tzinfo=timezone.get_current_timezone())
                    new_due = task.due_date.strftime('%d.%m.%Y %H:%M')
                except ValueError:
                    bot.send_message(message.chat.id, "❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ ЧЧ:ММ")
                    return
            task.save()
            text = ""
            bot.send_message(message.chat.id, text, reply_markup=TASK_MANAGEMENT_MARKUP)
        except Task.DoesNotExist:
            bot.send_message(message.chat.id, "❌ Задача не найдена")
        finally:
            clear_user_state(str(message.chat.id))
def show_assignee_selection_menu(chat_id: str, user_state: dict, call: CallbackQuery = None) -> None:
    due_date_text = ""
    if user_state.get('due_date'):
        due_date_text = f"\n⏰ Срок: {user_state['due_date'].strftime('%d.%m.%Y %H:%M')}"
    text = ""
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("👤 Назначить себе", callback_data="assign_to_creator"))
    markup.add(InlineKeyboardButton("👥 Выбрать исполнителя", callback_data="choose_assignee"))
    markup.add(InlineKeyboardButton("➡️ Пропустить", callback_data="skip_assignee"))
    markup.add(InlineKeyboardButton("⬅️ Отмена", callback_data="cancel_task_creation"))
    if call:
        bot.edit_message_text(chat_id=call.message.chat.id, text=text,
                             reply_markup=markup, message_id=call.message.message_id)
    else:
        bot.send_message(chat_id, text, reply_markup=markup)
def create_task_from_state(chat_id: str, user_state: dict) -> None:
    try:
        creator = get_or_create_user(chat_id)
        assignee_id = user_state.get('assignee_id')
        if assignee_id:
            assignee = User.objects.get(telegram_id=assignee_id)
        else:
            assignee = creator
        task = Task.objects.create(
            title=user_state['title'],
            description=user_state['description'],
            creator=creator,
            assignee=assignee,
            due_date=user_state.get('due_date'),
            status='active'
        )
        try:
            from bot.schedulers import schedule_task_reminder
            schedule_task_reminder(task)
        except Exception as e:
            print(f"Warning: Failed to schedule reminder for task {task.id}: {e}")
        due_date_text = ""
        if task.due_date:
            due_date_text = f"\n⏰ Срок: {task.due_date.strftime('%d.%m.%Y %H:%M')}"
        text = ""
        bot.send_message(chat_id, text, reply_markup=TASK_MANAGEMENT_MARKUP)
    except Exception as e:
        bot.send_message(chat_id, f"❌ Ошибка при создании задачи: {e}")
        print(f"Error creating task: {e}")
    finally:
        clear_user_state(chat_id)
@bot.callback_query_handler(func=lambda c: c.data.startswith("task_view_"))
def task_view_callback(call: CallbackQuery) -> None:
    try:
        parts = call.data.split('_')
        task_id = int(parts[2])
        view_type = parts[3] if len(parts) > 3 else 'assignee'
        task = Task.objects.get(id=task_id)
        is_creator_view = view_type == 'creator'
        require_creator = is_creator_view
        chat_id = get_chat_id_from_update(call)
        allowed, error_msg = check_permissions(chat_id, task, require_creator=require_creator)
        if not allowed:
            bot.answer_callback_query(call.id, error_msg, show_alert=True)
            return
        user = get_or_create_user(chat_id)
        is_creator = task.creator.telegram_id == user.telegram_id
        is_assignee = task.assignee.telegram_id == user.telegram_id
        show_task_progress(call.message.chat.id, task, is_creator, is_assignee)
    except (ValueError, ObjectDoesNotExist):
        bot.answer_callback_query(call.id, "Задача не найдена", show_alert=True)
    except Exception as e:
        bot.answer_callback_query(call.id, f"Ошибка: {e}", show_alert=True)
@bot.callback_query_handler(func=lambda c: c.data.startswith("task_progress_"))
def task_progress_callback(call: CallbackQuery) -> None:
    try:
        task_id = int(call.data.split('_')[2])
        task = Task.objects.get(id=task_id)
        chat_id = get_chat_id_from_update(call)
        allowed, error_msg = check_permissions(chat_id, task, require_creator=False)
        if not allowed:
            bot.answer_callback_query(call.id, error_msg, show_alert=True)
            return
        user = get_or_create_user(chat_id)
        is_creator = task.creator.telegram_id == user.telegram_id
        is_assignee = task.assignee.telegram_id == user.telegram_id
        subtasks = task.subtasks.all()
        if subtasks:
            text = ""
            markup = get_subtask_toggle_markup(task.id, subtasks)
            bot.edit_message_text(chat_id=call.message.chat.id, text=text,
                                reply_markup=markup, message_id=call.message.message_id)
        else:
            text = ""
            markup = get_task_actions_markup(task.id, task.status, task.report_attachments, is_creator, is_assignee)
            bot.edit_message_text(chat_id=call.message.chat.id, text=text,
                                reply_markup=markup, message_id=call.message.message_id)
    except (ValueError, ObjectDoesNotExist):
        bot.answer_callback_query(call.id, "Задача не найдена", show_alert=True)
@bot.callback_query_handler(func=lambda c: c.data.startswith("task_close_"))
def task_close_callback(call: CallbackQuery) -> None:
    try:
        task_id = int(call.data.split('_')[2])
        task = Task.objects.get(id=task_id)
        chat_id = get_chat_id_from_update(call)
        allowed, error_msg = check_permissions(chat_id, task, require_creator=False)
        if not allowed:
            bot.answer_callback_query(call.id, error_msg, show_alert=True)
            return
        initiate_task_close(chat_id, task)
    except (ValueError, ObjectDoesNotExist):
        bot.answer_callback_query(call.id, "Задача не найдена", show_alert=True)
@bot.callback_query_handler(func=lambda c: c.data.startswith("task_confirm_"))
def task_confirm_callback(call: CallbackQuery) -> None:
    try:
        task_id = int(call.data.split('_')[2])
        task = Task.objects.get(id=task_id)
        chat_id = get_chat_id_from_update(call)
        allowed, error_msg = check_permissions(chat_id, task, require_creator=True)
        if not allowed:
            bot.answer_callback_query(call.id, error_msg, show_alert=True)
            return
        task.status = 'completed'
        task.closed_at = timezone.now()
        task.save()
        try:
            from bot.schedulers import unschedule_task_reminder
            unschedule_task_reminder(task.id)
        except Exception as e:
            print(f"Warning: Failed to unschedule reminder for task {task.id}: {e}")
        try:
            bot.send_message(
                task.assignee.telegram_id,
                f"✅ Ваша задача подтверждена!\n\n{format_task_info(task)}"
            )
        except:
            pass
        text = ""
        bot.edit_message_text(chat_id=call.message.chat.id, text=text,
                            reply_markup=TASK_MANAGEMENT_MARKUP, message_id=call.message.message_id)
    except (ValueError, ObjectDoesNotExist):
        bot.answer_callback_query(call.id, "Задача не найдена", show_alert=True)
@bot.callback_query_handler(func=lambda c: c.data.startswith("task_reject_"))
def task_reject_callback(call: CallbackQuery) -> None:
    try:
        task_id = int(call.data.split('_')[2])
        task = Task.objects.get(id=task_id)
        chat_id = get_chat_id_from_update(call)
        allowed, error_msg = check_permissions(chat_id, task, require_creator=True)
        if not allowed:
            bot.answer_callback_query(call.id, error_msg, show_alert=True)
            return
        task.status = 'active'
        task.report_text = None
        task.report_attachments = []
        task.save()
        try:
            bot.send_message(
                task.assignee.telegram_id,
                f"❌ Ваша задача отклонена!\n\n{format_task_info(task)}\n\nПожалуйста, доработайте отчет."
            )
        except:
            pass
        text = ""
        bot.edit_message_text(chat_id=call.message.chat.id, text=text,
                            reply_markup=TASK_MANAGEMENT_MARKUP, message_id=call.message.message_id)
    except (ValueError, ObjectDoesNotExist):
        bot.answer_callback_query(call.id, "Задача не найдена", show_alert=True)
@bot.callback_query_handler(func=lambda c: c.data.startswith("subtask_toggle_"))
def subtask_toggle_callback(call: CallbackQuery) -> None:
    try:
        parts = call.data.split('_')
        task_id = int(parts[2])
        subtask_id = int(parts[3])
        task = Task.objects.get(id=task_id)
        subtask = Subtask.objects.get(id=subtask_id, task=task)
        chat_id = get_chat_id_from_update(call)
        allowed, error_msg = check_permissions(chat_id, task, require_creator=False)
        if not allowed:
            bot.answer_callback_query(call.id, error_msg, show_alert=True)
            return
        subtask.is_completed = not subtask.is_completed
        subtask.save()
        subtasks = task.subtasks.all()
        text = ""
        markup = get_subtask_toggle_markup(task.id, subtasks)
        bot.edit_message_text(chat_id=call.message.chat.id, text=text,
                            reply_markup=markup, message_id=call.message.message_id)
        bot.answer_callback_query(call.id, f"Подзадача {'✅ отмечена' if subtask.is_completed else '⏳ снята'}")
    except (ValueError, ObjectDoesNotExist):
        bot.answer_callback_query(call.id, "Подзадача не найдена", show_alert=True)
@bot.callback_query_handler(func=lambda c: c.data == "tasks_back")
def tasks_back_callback(call: CallbackQuery) -> None:
    tasks_command(call)
@bot.callback_query_handler(func=lambda c: c.data == "skip_description")
def skip_description_callback(call: CallbackQuery) -> None:
    user_state = get_user_state(str(call.message.chat.id))
    if not user_state or user_state.get('state') != 'waiting_task_description':
        bot.answer_callback_query(call.id, "Сессия истекла", show_alert=True)
        return
    user_state['description'] = None
    user_state['state'] = 'waiting_due_date'
    set_user_state(str(call.message.chat.id), user_state)
    text = ""
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Без срока", callback_data="skip_due_date"))
    markup.add(InlineKeyboardButton("⬅️ Отмена", callback_data="cancel_task_creation"))
    bot.edit_message_text(chat_id=call.message.chat.id, text=text,
                         reply_markup=markup, message_id=call.message.message_id)
@bot.callback_query_handler(func=lambda c: c.data == "skip_due_date")
def skip_due_date_callback(call: CallbackQuery) -> None:
    chat_id = get_chat_id_from_update(call)
    user_state = get_user_state(chat_id)
    if not user_state or user_state.get('state') != 'waiting_due_date':
        bot.answer_callback_query(call.id, "Сессия истекла", show_alert=True)
        return
    user_state['due_date'] = None
    user_state['state'] = 'waiting_assignee_selection'
    set_user_state(chat_id, user_state)
    show_assignee_selection_menu(chat_id, user_state, call)
@bot.callback_query_handler(func=lambda c: c.data == "assign_to_creator")
def assign_to_creator_callback(call: CallbackQuery) -> None:
    chat_id = get_chat_id_from_update(call)
    user_state = get_user_state(chat_id)
    if not user_state or user_state.get('state') != 'waiting_assignee_selection':
        bot.answer_callback_query(call.id, "Сессия истекла", show_alert=True)
        return
    create_task_from_state(chat_id, user_state)
@bot.callback_query_handler(func=lambda c: c.data == "skip_assignee")
def skip_assignee_callback(call: CallbackQuery) -> None:
    assign_to_creator_callback(call)
@bot.callback_query_handler(func=lambda c: c.data == "choose_assignee")
def choose_assignee_callback(call: CallbackQuery) -> None:
    chat_id = get_chat_id_from_update(call)
    user_state = get_user_state(chat_id)
    if not user_state or user_state.get('state') != 'waiting_assignee_selection':
        bot.answer_callback_query(call.id, "Сессия истекла", show_alert=True)
        return
    creator = get_or_create_user(chat_id)
    available_users = User.objects.all().order_by('user_name')
    if not available_users:
        text = "❌ Нет доступных пользователей для назначения"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("👤 Назначить себе", callback_data="assign_to_creator"))
        markup.add(InlineKeyboardButton("⬅️ Отмена", callback_data="cancel_task_creation"))
        bot.edit_message_text(chat_id=call.message.chat.id, text=text,
                             reply_markup=markup, message_id=call.message.message_id)
        return
    user_state['available_users'] = [user.telegram_id for user in available_users]
    user_state['current_page'] = 0
    set_user_state(chat_id, user_state)
    show_user_selection_page(call, 0)
@bot.callback_query_handler(func=lambda c: c.data.startswith("user_page_"))
def user_page_callback(call: CallbackQuery) -> None:
    chat_id = get_chat_id_from_update(call)
    user_state = get_user_state(chat_id)
    if not user_state or user_state.get('state') != 'waiting_assignee_selection':
        bot.answer_callback_query(call.id, "Сессия истекла", show_alert=True)
        return
    try:
        page = int(call.data.split('_')[2])
        show_user_selection_page(call, page)
        user_state['current_page'] = page
        set_user_state(chat_id, user_state)
    except (ValueError, IndexError):
        bot.answer_callback_query(call.id, "Ошибка обработки запроса")
def show_user_selection_page(call: CallbackQuery, page: int, users_per_page: int = 5) -> None:
    chat_id = get_chat_id_from_update(call)
    user_state = get_user_state(chat_id)
    if not user_state or user_state.get('state') != 'waiting_assignee_selection':
        bot.answer_callback_query(call.id, "Сессия истекла", show_alert=True)
        return
    available_user_ids = user_state.get('available_users', [])
    available_users = User.objects.filter(telegram_id__in=available_user_ids).order_by('user_name')
    start_idx = page * users_per_page
    end_idx = start_idx + users_per_page
    total_users = len(available_users)
    total_pages = (total_users + users_per_page - 1) // users_per_page
    if page >= total_pages or page < 0:
        bot.answer_callback_query(call.id, "Страница не найдена", show_alert=True)
        return
    users_on_page = available_users[start_idx:end_idx]
    showing_text = f"{start_idx + 1}-{min(end_idx, total_users)} из {total_users}"
    text = ""
    markup = InlineKeyboardMarkup()
    for user in users_on_page:
        role_emoji = "👑" if user.is_admin else "👨‍🎓"
        markup.add(InlineKeyboardButton(
            f"{role_emoji} {user.user_name}",
            callback_data=f"select_user_{user.telegram_id}"
        ))
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"user_page_{page-1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("Вперёд ➡️", callback_data=f"user_page_{page+1}"))
    if nav_buttons:
        markup.add(*nav_buttons)
    markup.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_assignee_selection"))
    bot.edit_message_text(chat_id=call.message.chat.id, text=text,
                         reply_markup=markup, message_id=call.message.message_id)
@bot.callback_query_handler(func=lambda c: c.data.startswith("select_user_"))
def select_user_callback(call: CallbackQuery) -> None:
    chat_id = get_chat_id_from_update(call)
    user_state = get_user_state(chat_id)
    if not user_state or user_state.get('state') != 'waiting_assignee_selection':
        bot.answer_callback_query(call.id, "Сессия истекла", show_alert=True)
        return
    try:
        selected_user_id = call.data.split('_')[2]
        available_user_ids = user_state.get('available_users', [])
        if selected_user_id not in available_user_ids:
            bot.answer_callback_query(call.id, "Пользователь не найден в списке", show_alert=True)
            return
        selected_user = User.objects.get(telegram_id=selected_user_id)
        user_state['assignee_id'] = selected_user_id
        create_task_from_state(chat_id, user_state)
    except User.DoesNotExist:
        bot.answer_callback_query(call.id, "Пользователь не найден", show_alert=True)
@bot.callback_query_handler(func=lambda c: c.data == "back_to_assignee_selection")
def back_to_assignee_selection_callback(call: CallbackQuery) -> None:
    chat_id = get_chat_id_from_update(call)
    user_state = get_user_state(chat_id)
    if not user_state:
        bot.answer_callback_query(call.id, "Сессия истекла", show_alert=True)
        return
    if 'available_users' in user_state:
        del user_state['available_users']
    if 'current_page' in user_state:
        del user_state['current_page']
    set_user_state(chat_id, user_state)
    due_date_text = ""
    if user_state.get('due_date'):
        due_date_text = f"\n⏰ Срок: {user_state['due_date'].strftime('%d.%m.%Y %H:%M')}"
    text = ""
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("👤 Назначить себе", callback_data="assign_to_creator"))
    markup.add(InlineKeyboardButton("👥 Выбрать исполнителя", callback_data="choose_assignee"))
    markup.add(InlineKeyboardButton("⬅️ Отмена", callback_data="cancel_task_creation"))
    bot.edit_message_text(chat_id=call.message.chat.id, text=text,
                         reply_markup=markup, message_id=call.message.message_id)
@bot.callback_query_handler(func=lambda c: c.data == "back_to_assignee_type")
def back_to_assignee_type_callback(call: CallbackQuery) -> None:
    back_to_assignee_selection_callback(call)
@bot.callback_query_handler(func=lambda c: c.data.startswith("view_report_attachments_"))
def view_report_attachments_callback(call: CallbackQuery) -> None:
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
@bot.callback_query_handler(func=lambda c: c.data.startswith("task_delete_"))
def task_delete_callback(call: CallbackQuery) -> None:
    try:
        task_id = int(call.data.split('_')[2])
        task = Task.objects.get(id=task_id)
        chat_id = get_chat_id_from_update(call)
        allowed, error_msg = check_permissions(chat_id, task, require_creator=True)
        if not allowed:
            bot.answer_callback_query(call.id, error_msg, show_alert=True)
            return
        text = ""
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("✅ Да, удалить", callback_data=f"confirm_delete_{task_id}"),
            InlineKeyboardButton("❌ Отмена", callback_data=f"task_progress_{task_id}")
        )
        bot.edit_message_text(chat_id=call.message.chat.id, text=text,
                             reply_markup=markup, message_id=call.message.message_id)
    except (ValueError, ObjectDoesNotExist):
        bot.answer_callback_query(call.id, "Задача не найдена", show_alert=True)
@bot.callback_query_handler(func=lambda c: c.data.startswith("confirm_delete_"))
def confirm_delete_callback(call: CallbackQuery) -> None:
    try:
        task_id = int(call.data.split('_')[2])
        task = Task.objects.get(id=task_id)
        chat_id = get_chat_id_from_update(call)
        allowed, error_msg = check_permissions(chat_id, task, require_creator=True)
        if not allowed:
            bot.answer_callback_query(call.id, error_msg, show_alert=True)
            return
        task_title = task.title
        task.delete()
        text = ""
        bot.edit_message_text(chat_id=call.message.chat.id, text=text,
                             reply_markup=TASK_MANAGEMENT_MARKUP, message_id=call.message.message_id)
    except (ValueError, ObjectDoesNotExist):
        bot.answer_callback_query(call.id, "Задача не найдена", show_alert=True)
@bot.callback_query_handler(func=lambda c: c.data.startswith("task_status_"))
def task_status_callback(call: CallbackQuery) -> None:
    try:
        task_id = int(call.data.split('_')[2])
        task = Task.objects.get(id=task_id)
        chat_id = get_chat_id_from_update(call)
        allowed, error_msg = check_permissions(chat_id, task, require_creator=False)
        if not allowed:
            bot.answer_callback_query(call.id, error_msg, show_alert=True)
            return
        status_info = {
            'active': '🔄 Задача активна и ждет выполнения',
            'pending_review': '⏳ Задача отправлена на проверку создателю',
            'completed': '✅ Задача выполнена и подтверждена',
            'cancelled': '❌ Задача отменена'
        }.get(task.status, '❓ Неизвестный статус')
        text = ""
        if task.status == 'pending_review':
            text += "\n\n⏳ Ожидайте подтверждения от создателя задачи."
        bot.edit_message_text(chat_id=call.message.chat.id, text=text, message_id=call.message.message_id)
    except (ValueError, ObjectDoesNotExist):
        bot.answer_callback_query(call.id, "Задача не найдена", show_alert=True)
def show_task_edit_menu(call: CallbackQuery, task: Task) -> None:
    text = ""
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📝 Название", callback_data=f"edit_title_{task.id}"))
    markup.add(InlineKeyboardButton("📋 Описание", callback_data=f"edit_description_{task.id}"))
    markup.add(InlineKeyboardButton("👤 Исполнителя", callback_data=f"edit_assignee_{task.id}"))
    markup.add(InlineKeyboardButton("⏰ Срок выполнения", callback_data=f"edit_due_date_{task.id}"))
    bot.edit_message_text(chat_id=call.message.chat.id, text=text,
                         reply_markup=markup, message_id=call.message.message_id)
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
        text = ""
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("⬅️ Отмена", callback_data=f"task_edit_{task_id}"))
        bot.edit_message_text(chat_id=call.message.chat.id, text=text,
                             reply_markup=markup, message_id=call.message.message_id)
        set_user_state(chat_id, {
            'state': 'editing_task_title',
            'task_id': task_id
        })
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
        text = ""
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("⬅️ Отмена", callback_data=f"task_edit_{task_id}"))
        bot.edit_message_text(chat_id=call.message.chat.id, text=text,
                             reply_markup=markup, message_id=call.message.message_id)
        set_user_state(chat_id, {
            'state': 'editing_task_description',
            'task_id': task_id
        })
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
        creator = get_or_create_user(chat_id)
        available_users = User.objects.exclude(telegram_id=creator.telegram_id).order_by('user_name')
        if not available_users:
            text = "❌ Нет других пользователей для назначения"
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("⬅️ Назад", callback_data=f"task_edit_{task_id}"))
            bot.edit_message_text(chat_id=call.message.chat.id, text=text,
                                 reply_markup=markup, message_id=call.message.message_id)
            return
        set_user_state(chat_id, {
            'state': 'editing_task_assignee',
            'task_id': task_id,
            'available_users': [user.telegram_id for user in available_users],
            'current_page': 0
        })
        show_assignee_selection_page(call, task, 0)
    except (ValueError, ObjectDoesNotExist):
        bot.answer_callback_query(call.id, "Задача не найдена", show_alert=True)
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
        current_due = task.due_date.strftime('%d.%m.%Y %H:%M') if task.due_date else "не указан"
        text = ""
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("⬅️ Отмена", callback_data=f"task_edit_{task_id}"))
        bot.edit_message_text(chat_id=call.message.chat.id, text=text,
                             reply_markup=markup, message_id=call.message.message_id)
        set_user_state(chat_id, {
            'state': 'editing_task_due_date',
            'task_id': task_id
        })
    except (ValueError, ObjectDoesNotExist):
        bot.answer_callback_query(call.id, "Задача не найдена", show_alert=True)
def show_assignee_selection_page(call: CallbackQuery, task: Task, page: int, users_per_page: int = 5) -> None:
    chat_id = get_chat_id_from_update(call)
    user_state = get_user_state(chat_id)
    if not user_state or user_state.get('state') != 'editing_task_assignee':
        bot.answer_callback_query(call.id, "Сессия истекла", show_alert=True)
        return
    available_user_ids = user_state.get('available_users', [])
    available_users = User.objects.filter(telegram_id__in=available_user_ids).order_by('user_name')
    start_idx = page * users_per_page
    end_idx = start_idx + users_per_page
    total_users = len(available_users)
    total_pages = (total_users + users_per_page - 1) // users_per_page
    if page >= total_pages or page < 0:
        bot.answer_callback_query(call.id, "Страница не найдена", show_alert=True)
        return
    users_on_page = available_users[start_idx:end_idx]
    showing_text = f"{start_idx + 1}-{min(end_idx, total_users)} из {total_users}"
    text = ""
    markup = InlineKeyboardMarkup()
    for user in users_on_page:
        role_emoji = "👑" if user.is_admin else "👨‍🎓"
        markup.add(InlineKeyboardButton(
            f"{role_emoji} {user.user_name}",
            callback_data=f"change_assignee_{task.id}_{user.telegram_id}"
        ))
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"assignee_page_{task.id}_{page-1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("Вперёд ➡️", callback_data=f"assignee_page_{task.id}_{page+1}"))
    if nav_buttons:
        markup.add(*nav_buttons)
    markup.add(InlineKeyboardButton("⬅️ Отмена", callback_data=f"task_edit_{task.id}"))
    bot.edit_message_text(chat_id=call.message.chat.id, text=text,
                         reply_markup=markup, message_id=call.message.message_id)
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
        user_state = get_user_state(chat_id)
        if user_state:
            user_state['current_page'] = page
            set_user_state(chat_id, user_state)
    except (ValueError, IndexError, ObjectDoesNotExist):
        bot.answer_callback_query(call.id, "Ошибка обработки запроса")
@bot.callback_query_handler(func=lambda c: c.data.startswith("change_assignee_"))
def change_assignee_callback(call: CallbackQuery) -> None:
    try:
        parts = call.data.split('_')
        task_id = int(parts[2])
        new_assignee_id = parts[3]
        task = Task.objects.get(id=task_id)
        new_assignee = User.objects.get(telegram_id=new_assignee_id)
        chat_id = get_chat_id_from_update(call)
        allowed, error_msg = check_permissions(chat_id, task, require_creator=True)
        if not allowed:
            bot.answer_callback_query(call.id, error_msg, show_alert=True)
            return
        user_state = get_user_state(chat_id)
        if not user_state or new_assignee_id not in user_state.get('available_users', []):
            bot.answer_callback_query(call.id, "Пользователь не найден в списке", show_alert=True)
            return
        old_assignee = task.assignee
        task.assignee = new_assignee
        task.save()
        try:
            bot.send_message(
                new_assignee.telegram_id,
                f"📋 ВАМ НАЗНАЧЕНА ЗАДАЧА\n\n{format_task_info(task)}"
            )
        except:
            pass
        clear_user_state(chat_id)
        text = ""
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("⬅️ К задачам", callback_data="my_created_tasks"))
        bot.edit_message_text(chat_id=call.message.chat.id, text=text,
                             reply_markup=markup, message_id=call.message.message_id)
    except (ValueError, ObjectDoesNotExist):
        bot.answer_callback_query(call.id, "Ошибка при смене исполнителя", show_alert=True)
@bot.callback_query_handler(func=lambda c: c.data == "cancel_task_creation")
def cancel_task_creation_callback(call: CallbackQuery) -> None:
    clear_user_state(str(call.message.chat.id))
    text = "❌ Создание задачи отменено"
    bot.edit_message_text(chat_id=call.message.chat.id, text=text,
                         reply_markup=TASK_MANAGEMENT_MARKUP, message_id=call.message.message_id)