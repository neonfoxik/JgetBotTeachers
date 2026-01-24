from bot.handlers.utils import (
    get_or_create_user, get_chat_id_from_update, safe_edit_or_send_message, format_task_info,
    check_permissions, show_task_progress, check_registration
)
from bot.models import Task


def check_all_subtasks_completed(task: Task) -> tuple[bool, str]:
    """
    Проверяет, все ли подзадачи выполнены
    Возвращает (все_выполнены, сообщение_ошибки)
    """
    subtasks = task.subtasks.all()
    if not subtasks:
        return True, ""  # Если подзадач нет, то проверка пройдена

    completed_count = subtasks.filter(is_completed=True).count()
    total_count = subtasks.count()

    if completed_count == total_count:
        return True, ""
    else:
        incomplete_count = total_count - completed_count
        return False, f"❌ Невозможно закрыть задачу! {incomplete_count} подзадач из {total_count} не выполнены."
from bot.handlers.tasks import initiate_task_close
from bot import bot, logger
from bot.models import User, Task, Subtask
from bot.keyboards import (
    get_task_actions_markup, get_subtask_toggle_markup,
    TASK_MANAGEMENT_MARKUP
)
from telebot.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone


def task_view_callback(call: CallbackQuery) -> None:
    if not check_registration(call):
        return
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
        # Исполнителем считается любой, кто имеет доступ (лично или через роль)
        is_assignee = task.has_access(user)
        show_task_progress(call.message.chat.id, task, is_creator, is_assignee, call.message.message_id)
    except (ValueError, ObjectDoesNotExist):
        bot.answer_callback_query(call.id, "Задача не найдена", show_alert=True)
    except Exception as e:
        bot.answer_callback_query(call.id, f"Ошибка: {e}", show_alert=True)


def task_progress_callback(call: CallbackQuery) -> None:
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
        user = get_or_create_user(chat_id)
        is_creator = task.creator.telegram_id == user.telegram_id
        is_assignee = task.has_access(user)
        show_task_progress(chat_id, task, is_creator, is_assignee, call.message.message_id)
    except (ValueError, ObjectDoesNotExist):
        bot.answer_callback_query(call.id, "Задача не найдена", show_alert=True)


def task_complete_callback(call: CallbackQuery) -> None:
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

        if task.status != 'active':
            bot.answer_callback_query(call.id, f"Задача уже имеет статус '{task.get_status_display()}'", show_alert=True)
            return

        # Проверяем, все ли подзадачи выполнены
        all_completed, error_msg = check_all_subtasks_completed(task)
        if not all_completed:
            bot.answer_callback_query(call.id, error_msg, show_alert=True)
            return

        user = get_or_create_user(chat_id)
        is_creator = task.creator.telegram_id == user.telegram_id

        if is_creator:
            # Если создатель завершает задачу напрямую
            task.status = 'completed'
            task.closed_at = timezone.now()
            task.save()
            text = f"✅ Задача '{task.title}' отмечена как выполненная!"
        else:
            # Если исполнитель отправляет на проверку
            task.status = 'pending_review'
            task.save()
            text = f"📤 Задача '{task.title}' отправлена на проверку создателю"

            # Уведомляем создателя
            try:
                creator_notification = f"📬 Ваша задача готова к проверке\n\n{format_task_info(task)}"
                markup = get_task_actions_markup(task.id, task.status, task.report_attachments, True, False)
                bot.send_message(task.creator.telegram_id, creator_notification, reply_markup=markup)
            except Exception as e:
                logger.error(f"Не удалось уведомить создателя задачи {task_id}: {e}")

        safe_edit_or_send_message(chat_id, text, reply_markup=TASK_MANAGEMENT_MARKUP, message_id=call.message.message_id)

        # Проверка туториала
        from bot.handlers.utils import get_user_state
        u_state = get_user_state(chat_id)
        if u_state and u_state.get('state') == 'tutorial_waiting_for_completion':
            if task.id == u_state.get('tutorial_task_id'):
                from bot.handlers.tutorial import finish_tutorial
                finish_tutorial(chat_id, call.message.message_id)

    except (ValueError, ObjectDoesNotExist):
        bot.answer_callback_query(call.id, "Задача не найдена", show_alert=True)


def task_confirm_callback(call: CallbackQuery) -> None:
    if not check_registration(call):
        return
    try:
        task_id = int(call.data.split('_')[2])
        task = Task.objects.get(id=task_id)
        chat_id = get_chat_id_from_update(call)
        allowed, error_msg = check_permissions(chat_id, task, require_creator=True)
        if not allowed:
            bot.answer_callback_query(call.id, error_msg, show_alert=True)
            return

        if task.status != 'pending_review':
            bot.answer_callback_query(call.id, f"Задача не ожидает подтверждения", show_alert=True)
            return

        task.status = 'completed'
        task.closed_at = timezone.now()
        task.save()

        # Логируем в историю
        from bot.handlers.utils import log_task_history
        user = User.objects.get(telegram_id=chat_id)
        log_task_history(task, user, "Выполнение подтверждено создателем")

        text = f"✅ Задача '{task.title}' подтверждена и завершена!"

        # Уведомляем исполнителей
        try:
            assignee_notification = f"🎉 Ваша задача подтверждена!\n\n{format_task_info(task)}"
            for assignee in task.get_assignees():
                if assignee.telegram_id != chat_id: # Не уведомляем того, кто подтвердил (хотя подтверждает создатель)
                    bot.send_message(assignee.telegram_id, assignee_notification)
        except Exception as e:
            logger.error(f"Не удалось уведомить исполнителей задачи {task_id}: {e}")

        safe_edit_or_send_message(chat_id, text, reply_markup=TASK_MANAGEMENT_MARKUP, message_id=call.message.message_id)

    except (ValueError, ObjectDoesNotExist):
        bot.answer_callback_query(call.id, "Задача не найдена", show_alert=True)


def task_reject_callback(call: CallbackQuery) -> None:
    if not check_registration(call):
        return
    try:
        task_id = int(call.data.split('_')[2])
        task = Task.objects.get(id=task_id)
        chat_id = get_chat_id_from_update(call)
        allowed, error_msg = check_permissions(chat_id, task, require_creator=True)
        if not allowed:
            bot.answer_callback_query(call.id, error_msg, show_alert=True)
            return

        if task.status != 'pending_review':
            bot.answer_callback_query(call.id, f"Задача не ожидает подтверждения", show_alert=True)
            return

        task.status = 'active'
        task.report_text = None
        task.report_attachments.clear()
        task.save()

        text = f"❌ Задача '{task.title}' возвращена на доработку"

        # Уведомляем исполнителей
        try:
            assignee_notification = f"🔄 Ваша задача возвращена на доработку\n\n{format_task_info(task)}\n\n💬 Комментарий: Нужно доработать"
            markup = get_task_actions_markup(task.id, task.status, task.report_attachments, False, True)
            for assignee in task.get_assignees():
                bot.send_message(assignee.telegram_id, assignee_notification, reply_markup=markup)
        except Exception as e:
            logger.error(f"Не удалось уведомить исполнителей задачи {task_id}: {e}")

        safe_edit_or_send_message(chat_id, text, reply_markup=TASK_MANAGEMENT_MARKUP, message_id=call.message.message_id)

    except (ValueError, ObjectDoesNotExist):
        bot.answer_callback_query(call.id, "Задача не найдена", show_alert=True)


def subtask_toggle_callback(call: CallbackQuery) -> None:
    if not check_registration(call):
        return
    try:
        parts = call.data.split('_')
        task_id = int(parts[2])
        subtask_id = int(parts[3])

        task = Task.objects.get(id=task_id)
        subtask = task.subtasks.get(id=subtask_id)

        chat_id = get_chat_id_from_update(call)
        allowed, error_msg = check_permissions(chat_id, task, require_creator=False)
        if not allowed:
            bot.answer_callback_query(call.id, error_msg, show_alert=True)
            return

        # Переключаем статус подзадачи
        subtask.is_completed = not subtask.is_completed
        if subtask.is_completed:
            subtask.completed_at = timezone.now()
        else:
            subtask.completed_at = None
        subtask.save()

        # Показываем обновленный вид задачи с прогрессом
        user = get_or_create_user(chat_id)
        is_creator = task.creator.telegram_id == user.telegram_id
        is_assignee = task.has_access(user)
        show_task_progress(chat_id, task, is_creator, is_assignee, call.message.message_id)

        # Показываем уведомление о переключении
        status_text = "выполнена" if subtask.is_completed else "не выполнена"
        bot.answer_callback_query(call.id, f"✅ Подзадача отмечена как {status_text}", show_alert=False)

    except (ValueError, ObjectDoesNotExist):
        bot.answer_callback_query(call.id, "Подзадача не найдена", show_alert=True)


def task_delete_callback(call: CallbackQuery) -> None:
    if not check_registration(call):
        return
    try:
        task_id = int(call.data.split('_')[2])
        task = Task.objects.get(id=task_id)
        chat_id = get_chat_id_from_update(call)
        # Удаление может делать только создатель
        allowed, error_msg = check_permissions(chat_id, task, require_creator=True)
        if not allowed:
            bot.answer_callback_query(call.id, error_msg, show_alert=True)
            return

        text = f"🗑️ УДАЛЕНИЕ ЗАДАЧИ\n\nВы действительно хотите удалить задачу '{task.title}'?\n\n⚠️ Это действие нельзя отменить!"
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("✅ Да, удалить", callback_data=f"confirm_delete_{task_id}"),
            InlineKeyboardButton("❌ Отмена", callback_data=f"task_progress_{task_id}")
        )
        safe_edit_or_send_message(call.message.chat.id, text, reply_markup=markup, message_id=call.message.message_id)

        # Подтверждаем callback
        bot.answer_callback_query(call.id)

    except (ValueError, ObjectDoesNotExist) as e:
        logger.error(f"Error in task_delete_callback: {e}")
        bot.answer_callback_query(call.id, "Задача не найдена", show_alert=True)
    except Exception as e:
        logger.error(f"Unexpected error in task_delete_callback: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка", show_alert=True)


def confirm_delete_callback(call: CallbackQuery) -> None:
    if not check_registration(call):
        return
    try:
        task_id = int(call.data.split('_')[2])
        task = Task.objects.get(id=task_id)
        chat_id = get_chat_id_from_update(call)
        # Удаление может делать только создатель
        allowed, error_msg = check_permissions(chat_id, task, require_creator=True)
        if not allowed:
            bot.answer_callback_query(call.id, error_msg, show_alert=True)
            return

        task_title = task.title
        try:
            task.delete()
            text = f"✅ Задача '{task_title}' успешно удалена из базы данных"
            safe_edit_or_send_message(call.message.chat.id, text, reply_markup=TASK_MANAGEMENT_MARKUP, message_id=call.message.message_id)

            # Подтверждаем callback
            bot.answer_callback_query(call.id, "Задача удалена", show_alert=False)

        except Exception as e:
            logger.error(f"Ошибка при удалении задачи {task_id}: {e}")
            text = f"❌ Ошибка при удалении задачи '{task_title}': {str(e)}"
            safe_edit_or_send_message(call.message.chat.id, text, reply_markup=TASK_MANAGEMENT_MARKUP, message_id=call.message.message_id)
            bot.answer_callback_query(call.id, "Ошибка при удалении", show_alert=True)

    except (ValueError, ObjectDoesNotExist) as e:
        logger.error(f"Error in confirm_delete_callback: {e}")
        bot.answer_callback_query(call.id, "Задача не найдена", show_alert=True)
    except Exception as e:
        logger.error(f"Unexpected error in confirm_delete_callback: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка", show_alert=True)


def task_status_callback(call: CallbackQuery) -> None:
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

        status_info = f"📊 Статус задачи\n\n{format_task_info(task, show_details=True)}"

        if task.status == 'pending_review' and task.report_text:
            status_info += f"\n📄 Отчет исполнителя:\n{task.report_text}"

        markup = get_task_actions_markup(task.id, task.status, task.report_attachments,
                                       task.creator.telegram_id == chat_id,
                                       task.has_access(get_or_create_user(chat_id)))
        safe_edit_or_send_message(call.message.chat.id, status_info, reply_markup=markup, message_id=call.message.message_id)

    except (ValueError, ObjectDoesNotExist):
        bot.answer_callback_query(call.id, "Задача не найдена", show_alert=True)


def task_close_callback(call: CallbackQuery) -> None:
    """Обработчик нажатия кнопки 'Отправить на проверку'"""
    if not check_registration(call):
        return
    logger.info("=== TASK_CLOSE_CALLBACK STARTED ===")
    logger.info(f"Callback data: {call.data}")

    try:
        # Парсим task_id
        parts = call.data.split('_')
        if len(parts) < 3:
            logger.error(f"Invalid callback data format: {call.data}")
            bot.answer_callback_query(call.id, "❌ Неверный формат данных", show_alert=True)
            return

        task_id = int(parts[2])
        logger.info(f"Task ID: {task_id}")

        # Получаем задачу
        task = Task.objects.get(id=task_id)
        logger.info(f"Task found: {task.title}")

        # Получаем chat_id
        chat_id = str(call.message.chat.id)
        logger.info(f"Chat ID: {chat_id}")

        # Проверяем права
        allowed, error_msg = check_permissions(chat_id, task, require_creator=False)
        if not allowed:
            logger.warning(f"Permission denied: {error_msg}")
            bot.answer_callback_query(call.id, error_msg, show_alert=True)
            return

        # Получаем пользователя
        user = get_or_create_user(chat_id)
        logger.info(f"User: {user.user_name}")

        # Проверяем, что пользователь является исполнителем (лично или через роль)
        if not task.has_access(user):
            logger.warning(f"User {user.telegram_id} has no access to task {task.id}")
            bot.answer_callback_query(call.id, "❌ Только исполнитель может отправить задачу на проверку", show_alert=True)
            return

        # Проверяем статус задачи
        if task.status == 'pending_review':
            logger.info("Task already in pending_review")
            bot.answer_callback_query(call.id, "ℹ️ Задача уже отправлена на проверку", show_alert=False)
            return

        if task.status != 'active':
            logger.warning(f"Task status is {task.status}, not active")
            bot.answer_callback_query(call.id, f"❌ Невозможно отправить задачу в статусе '{task.get_status_display()}'", show_alert=True)
            return

        # Проверяем, все ли подзадачи выполнены
        all_completed, error_msg = check_all_subtasks_completed(task)
        if not all_completed:
            logger.warning(f"Task {task.id} cannot be closed: not all subtasks completed")
            bot.answer_callback_query(call.id, error_msg, show_alert=True)
            return

        # Отправляем задачу на проверку
        logger.info("Calling initiate_task_close")
        initiate_task_close(chat_id, task, call.message.message_id)

        # Отвечаем на callback
        logger.info("Answering callback query with success")
        bot.answer_callback_query(call.id, "✅ Задача отправлена на проверку", show_alert=False)
        logger.info("=== TASK_CLOSE_CALLBACK COMPLETED ===")

    except ValueError as e:
        logger.error(f"ValueError in task_close_callback: {e}")
        bot.answer_callback_query(call.id, "❌ Неверный формат данных", show_alert=True)
    except Task.DoesNotExist as e:
        logger.error(f"Task not found: {e}")
        bot.answer_callback_query(call.id, "❌ Задача не найдена", show_alert=True)
    except Exception as e:
        logger.error(f"Unexpected error in task_close_callback: {e}")
        import traceback
        logger.error(traceback.format_exc())
        try:
            bot.answer_callback_query(call.id, "❌ Произошла ошибка", show_alert=True)
        except Exception as answer_error:
            logger.error(f"Failed to answer callback: {answer_error}")
        logger.info("=== TASK_CLOSE_CALLBACK FAILED ===")


def view_task_attachments_callback(call: CallbackQuery) -> None:
    """Обработчик просмотра вложений, добавленных при создании задачи"""
    try:
        task_id = int(call.data.split('_')[3])
        task = Task.objects.get(id=task_id)
        chat_id = get_chat_id_from_update(call)
        
        allowed, error_msg = check_permissions(chat_id, task, require_creator=False)
        if not allowed:
            bot.answer_callback_query(call.id, error_msg, show_alert=True)
            return

        if not task.attachments:
            bot.answer_callback_query(call.id, "Нет вложений в задаче", show_alert=True)
            return

        # Отправляем все вложения
        bot.answer_callback_query(call.id, f"Отправляю вложения ({len(task.attachments)} шт.)...")
        
        for attachment in task.attachments:
            try:
                if attachment['type'] == 'photo':
                    bot.send_photo(call.message.chat.id, attachment['file_id'])
                elif attachment['type'] == 'document':
                    bot.send_document(call.message.chat.id, attachment['file_id'])
            except Exception as e:
                logger.error(f"Ошибка при отправке вложения задачи {task.id}: {e}")

    except (ValueError, ObjectDoesNotExist, IndexError):
        bot.answer_callback_query(call.id, "Задача не найдена", show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка в view_task_attachments_callback: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка при получении вложений", show_alert=True)
