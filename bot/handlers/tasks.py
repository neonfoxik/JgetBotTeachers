from datetime import datetime, timedelta
from django.utils import timezone
from bot import bot, logger
from bot.models import User, Task, Subtask, UserState
from bot.keyboards import (
    get_task_actions_markup, get_task_confirmation_markup,
    get_subtask_toggle_markup, get_tasks_list_markup, get_user_selection_markup,
    TASK_MANAGEMENT_MARKUP, UNIVERSAL_BUTTONS, main_markup, get_main_menu
)
from bot.handlers.utils import (
    get_or_create_user, get_chat_id_from_update, safe_edit_or_send_message, get_user_state,
    set_user_state, clear_user_state, check_permissions, format_task_info, show_task_progress,
    check_registration
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

def my_created_tasks_command(message: Message) -> None:
    my_created_tasks_command_logic(message)

def my_created_tasks_callback(call: CallbackQuery) -> None:
    try:
        # Проверяем, находится ли пользователь уже в разделе "мои задачи"
        current_text = getattr(call.message, 'text', '') or getattr(call.message, 'caption', '') or ''
        logger.info(f"Current message text: '{current_text[:50]}...'")

        if "ЗАДАЧИ, СОЗДАННЫЕ ВАМИ" in current_text:
            # Показываем уведомление, что пользователь уже в этом разделе
            logger.info("User already in my tasks section, showing notification")
            bot.answer_callback_query(
                call.id,
                "ℹ️ Вы уже находитесь в разделе 'Мои задачи'",
                show_alert=False
            )
            return

        logger.info("User not in my tasks section, loading tasks...")
        chat_id = get_chat_id_from_update(call)
        user = get_or_create_user(chat_id)
        created_tasks = Task.objects.filter(creator=user).order_by('-created_at')

        if not created_tasks:
            logger.info("No tasks found, editing message")
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                text="📋 Вы еще не создали ни одной задачи",
                reply_markup=UNIVERSAL_BUTTONS,
                message_id=call.message.message_id
            )
            return

        text = f"📋 ЗАДАЧИ, СОЗДАННЫЕ ВАМИ\n\n"
        markup = get_tasks_list_markup(created_tasks, is_creator_view=True)

        logger.info("Editing message with tasks list")
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            text=text,
            reply_markup=markup,
            message_id=call.message.message_id
        )
        logger.info("Message edited successfully")

    except Exception as e:
        logger.error(f"Error in my_created_tasks_callback: {e}")
        import traceback
        logger.error(traceback.format_exc())
        try:
            bot.answer_callback_query(call.id, "Произошла ошибка", show_alert=True)
        except:
            pass
def my_created_tasks_command_logic(update) -> None:
    if not check_registration(update):
        return
    chat_id = get_chat_id_from_update(update)
    user = get_or_create_user(chat_id)
    created_tasks = Task.objects.filter(creator=user).order_by('-created_at')
    if not created_tasks:
        text = "📋 Вы еще не создали ни одной задачи"
        markup = UNIVERSAL_BUTTONS
    else:
        text = f"📋 ЗАДАЧИ, СОЗДАННЫЕ ВАМИ\n\n"
        markup = get_tasks_list_markup(created_tasks, is_creator_view=True)

    # Если это callback (есть message в update), редактируем сообщение
    if hasattr(update, 'message') and hasattr(update.message, 'message_id'):
        safe_edit_or_send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=markup,
            message_id=update.message.message_id
        )
    else:
        # Если это команда, отправляем новое сообщение
        safe_edit_or_send_message(chat_id, text, reply_markup=markup)
def create_task_command_logic(update) -> None:
    if not check_registration(update):
        return
    chat_id = get_chat_id_from_update(update)
    logger.info(f"Начало создания задачи для пользователя {chat_id}")
    
    user_state = get_user_state(chat_id) or {}
    is_tutorial = user_state.get('state') == 'tutorial_waiting_for_creation'
    
    text = "📝 **ШАГ 1: НАЗВАНИЕ**\n\n🎯 Введите название задачи.\n\n"
    if is_tutorial:
        text += "_Например: 'Купить продукты' или 'Подготовить отчет'. Это то, что будет отображаться в списке._"
    else:
        text += "Введите краткое описание того, что нужно сделать:"
        
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("⬅️ Отмена", callback_data="main_menu"))
    
    message_id = update.message.message_id if hasattr(update, 'message') else None
    safe_edit_or_send_message(chat_id, text, reply_markup=markup, message_id=message_id, parse_mode='Markdown')

    new_state = {'state': 'waiting_task_title'}
    
    new_state = {'state': 'waiting_task_title'}
    if is_tutorial:
        new_state['is_tutorial'] = True
        
    set_user_state(chat_id, new_state)
    logger.info(f"Установлено состояние 'waiting_task_title' для пользователя {chat_id}")

# Обработчик close_task перенесен в commands.py
# Обработчик task_progress перенесен в commands.py
# Обработчик debug перенесен в commands.py

def initiate_task_close(chat_id: str, task: Task, message_id: int = None) -> None:
    """Инициирует процесс закрытия задачи"""
    try:
        if task.status not in ['active', 'pending_review']:
            safe_edit_or_send_message(chat_id, f"❌ Невозможно закрыть задачу в статусе '{task.get_status_display()}'", message_id=message_id)
            return

        # Проверяем, все ли подзадачи выполнены
        from bot.handlers.task_actions import check_all_subtasks_completed
        all_completed, error_msg = check_all_subtasks_completed(task)
        if not all_completed:
            safe_edit_or_send_message(chat_id, error_msg, message_id=message_id)
            return

        if task.creator.telegram_id == task.assignee.telegram_id:
            # Создатель и исполнитель - один человек, закрываем задачу сразу
            task.status = 'completed'
            task.closed_at = timezone.now()
            task.save()

            try:
                from bot.schedulers import unschedule_task_reminder
                unschedule_task_reminder(task.id)
            except Exception as e:
                print(f"Warning: Failed to unschedule reminder for task {task.id}: {e}")

            text = f"✅ Задача закрыта\n\n{format_task_info(task)}\n\nЗадача успешно закрыта!"
            user = get_or_create_user(chat_id)
            safe_edit_or_send_message(chat_id, text, reply_markup=get_main_menu(user), message_id=message_id)
        else:
            # Отправляем запрос на отчет
            text = f"📄 **Отправка отчета по задаче**\n\n{format_task_info(task)}\n\n"
            text += "Опишите что было сделано (минимум 10 символов) или прикрепите фото/файлы:"

            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("⬅️ Отмена", callback_data=f"task_progress_{task.id}"))

            # Пытаемся редактировать, если есть message_id, иначе отправляем новое
            safe_edit_or_send_message(chat_id, text, reply_markup=markup, message_id=message_id, parse_mode='Markdown')

            set_user_state(chat_id, {
                'state': 'waiting_report',
                'report_task_id': task.id
            })
    except Exception as e:
        logger.error(f"Error in initiate_task_close: {e}", exc_info=True)
        try:
            bot.send_message(chat_id, "❌ Произошла ошибка при отправке задачи на проверку")
        except:
            pass
