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
from telebot.types import CallbackQuery
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone


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
        show_task_progress(call.message.chat.id, task, is_creator, is_assignee, call.message.message_id)
    except (ValueError, ObjectDoesNotExist):
        bot.answer_callback_query(call.id, "Задача не найдена", show_alert=True)
    except Exception as e:
        bot.answer_callback_query(call.id, f"Ошибка: {e}", show_alert=True)


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
            text = format_task_info(task, show_details=True)
            text += "\n\n📋 ПОДЗАДАЧИ:"
            for subtask in subtasks:
                status = "✅" if subtask.is_completed else "⏳"
                completed_date = f" ({subtask.completed_at.strftime('%d.%m.%Y')})" if subtask.completed_at else ""
                text += f"\n{status} {subtask.title}{completed_date}"
            markup = get_subtask_toggle_markup(task.id, subtasks)
            safe_edit_or_send_message(call.message.chat.id, text, reply_markup=markup, message_id=call.message.message_id)
        else:
            text = format_task_info(task, show_details=True)
            markup = get_task_actions_markup(task.id, task.status, task.report_attachments, is_creator, is_assignee)
            safe_edit_or_send_message(call.message.chat.id, text, reply_markup=markup, message_id=call.message.message_id)
    except (ValueError, ObjectDoesNotExist):
        bot.answer_callback_query(call.id, "Задача не найдена", show_alert=True)


def task_complete_callback(call: CallbackQuery) -> None:
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
                creator_notification = f"📬 ВАША ЗАДАЧА ГОТОВА К ПРОВЕРКЕ\n\n{format_task_info(task)}"
                markup = get_task_actions_markup(task.id, task.status, task.report_attachments, True, False)
                bot.send_message(task.creator.telegram_id, creator_notification, reply_markup=markup)
            except Exception as e:
                logger.error(f"Не удалось уведомить создателя задачи {task_id}: {e}")

        safe_edit_or_send_message(chat_id, text, reply_markup=TASK_MANAGEMENT_MARKUP, message_id=call.message.message_id)

    except (ValueError, ObjectDoesNotExist):
        bot.answer_callback_query(call.id, "Задача не найдена", show_alert=True)


def task_confirm_callback(call: CallbackQuery) -> None:
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

        text = f"✅ Задача '{task.title}' подтверждена и завершена!"

        # Уведомляем исполнителя
        try:
            assignee_notification = f"🎉 ВАША ЗАДАЧА ПОДТВЕРЖДЕНА!\n\n{format_task_info(task)}"
            bot.send_message(task.assignee.telegram_id, assignee_notification)
        except Exception as e:
            logger.error(f"Не удалось уведомить исполнителя задачи {task_id}: {e}")

        safe_edit_or_send_message(chat_id, text, reply_markup=TASK_MANAGEMENT_MARKUP, message_id=call.message.message_id)

    except (ValueError, ObjectDoesNotExist):
        bot.answer_callback_query(call.id, "Задача не найдена", show_alert=True)


def task_reject_callback(call: CallbackQuery) -> None:
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

        # Уведомляем исполнителя
        try:
            assignee_notification = f"🔄 ВАША ЗАДАЧА ВОЗВРАЩЕНА НА ДОРАБОТКУ\n\n{format_task_info(task)}\n\n💬 Комментарий: Нужно доработать"
            markup = get_task_actions_markup(task.id, task.status, task.report_attachments, False, True)
            bot.send_message(task.assignee.telegram_id, assignee_notification, reply_markup=markup)
        except Exception as e:
            logger.error(f"Не удалось уведомить исполнителя задачи {task_id}: {e}")

        safe_edit_or_send_message(chat_id, text, reply_markup=TASK_MANAGEMENT_MARKUP, message_id=call.message.message_id)

    except (ValueError, ObjectDoesNotExist):
        bot.answer_callback_query(call.id, "Задача не найдена", show_alert=True)


def subtask_toggle_callback(call: CallbackQuery) -> None:
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

        subtask.is_completed = not subtask.is_completed
        if subtask.is_completed:
            subtask.completed_at = timezone.now()
        else:
            subtask.completed_at = None
        subtask.save()

        # Показываем обновленный список подзадач
        subtasks = task.subtasks.all()
        text = format_task_info(task, show_details=True)
        text += "\n\n📋 ПОДЗАДАЧИ:"
        for sub in subtasks:
            status = "✅" if sub.is_completed else "⏳"
            completed_date = f" ({sub.completed_at.strftime('%d.%m.%Y')})" if sub.completed_at else ""
            text += f"\n{status} {sub.title}{completed_date}"

        markup = get_subtask_toggle_markup(task.id, subtasks)
        safe_edit_or_send_message(call.message.chat.id, text, reply_markup=markup, message_id=call.message.message_id)

    except (ValueError, ObjectDoesNotExist):
        bot.answer_callback_query(call.id, "Подзадача не найдена", show_alert=True)


def task_delete_callback(call: CallbackQuery) -> None:
    try:
        task_id = int(call.data.split('_')[2])
        task = Task.objects.get(id=task_id)
        chat_id = get_chat_id_from_update(call)
        # Удаление могут делать создатель и исполнитель для любой задачи
        allowed, error_msg = check_permissions(chat_id, task, require_creator=False)
        if not allowed:
            bot.answer_callback_query(call.id, error_msg, show_alert=True)
            return
        text = ""
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("✅ Да, удалить", callback_data=f"confirm_delete_{task_id}"),
            InlineKeyboardButton("❌ Отмена", callback_data=f"task_progress_{task_id}")
        )
        safe_edit_or_send_message(call.message.chat.id, text, reply_markup=markup, message_id=call.message.message_id)
    except (ValueError, ObjectDoesNotExist):
        bot.answer_callback_query(call.id, "Задача не найдена", show_alert=True)


def confirm_delete_callback(call: CallbackQuery) -> None:
    try:
        task_id = int(call.data.split('_')[2])
        task = Task.objects.get(id=task_id)
        chat_id = get_chat_id_from_update(call)
        # Удаление могут делать создатель и исполнитель для любой задачи
        allowed, error_msg = check_permissions(chat_id, task, require_creator=False)
        if not allowed:
            bot.answer_callback_query(call.id, error_msg, show_alert=True)
            return
        task_title = task.title
        try:
            task.delete()
            text = f"✅ Задача '{task_title}' успешно удалена из базы данных"
            safe_edit_or_send_message(call.message.chat.id, text, reply_markup=TASK_MANAGEMENT_MARKUP, message_id=call.message.message_id)
        except Exception as e:
            logger.error(f"Ошибка при удалении задачи {task_id}: {e}")
            text = f"❌ Ошибка при удалении задачи '{task_title}': {str(e)}"
            safe_edit_or_send_message(call.message.chat.id, text, reply_markup=TASK_MANAGEMENT_MARKUP, message_id=call.message.message_id)
    except (ValueError, ObjectDoesNotExist):
        bot.answer_callback_query(call.id, "Задача не найдена", show_alert=True)


def task_status_callback(call: CallbackQuery) -> None:
    try:
        task_id = int(call.data.split('_')[2])
        task = Task.objects.get(id=task_id)
        chat_id = get_chat_id_from_update(call)
        allowed, error_msg = check_permissions(chat_id, task, require_creator=False)
        if not allowed:
            bot.answer_callback_query(call.id, error_msg, show_alert=True)
            return

        status_info = f"📊 СТАТУС ЗАДАЧИ\n\n{format_task_info(task, show_details=True)}"

        if task.status == 'pending_review' and task.report_text:
            status_info += f"\n📄 ОТЧЕТ ИСПОЛНИТЕЛЯ:\n{task.report_text}"

        markup = get_task_actions_markup(task.id, task.status, task.report_attachments,
                                       task.creator.telegram_id == chat_id,
                                       task.assignee.telegram_id == chat_id)
        safe_edit_or_send_message(call.message.chat.id, status_info, reply_markup=markup, message_id=call.message.message_id)

    except (ValueError, ObjectDoesNotExist):
        bot.answer_callback_query(call.id, "Задача не найдена", show_alert=True)
