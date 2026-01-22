from bot.handlers.utils import (
    get_or_create_user, get_chat_id_from_update, safe_edit_or_send_message, format_task_info,
    check_permissions, get_user_state, set_user_state, clear_user_state
)
from bot.handlers.main import show_task_progress
from bot import bot, logger
from bot.models import User, Task, TaskComment
from bot.keyboards import (
    get_task_actions_markup, TASK_MANAGEMENT_MARKUP
)
from telebot.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone


# initiate_task_close перенесена в tasks.py и унифицирована


def handle_task_report(message: Message) -> None:
    chat_id = str(message.chat.id)
    user = get_or_create_user(chat_id)
    user_state = get_user_state(chat_id)

    if not user_state or user_state.get('state') != 'waiting_report':
        return

    task_id = user_state.get('report_task_id')
    if not task_id:
        clear_user_state(chat_id)
        return

    try:
        active_task = Task.objects.get(id=task_id)

        # Обрабатываем текстовый отчет или подпись к фото
        new_text = ""
        if message.text and not message.text.startswith('/'):
            new_text = message.text.strip()
        elif message.caption:
            new_text = message.caption.strip()

        # Получаем накопленный текст отчета из состояния
        report_text = user_state.get('report_text', '')
        if new_text:
            if report_text:
                report_text += f"\n{new_text}"
            else:
                report_text = new_text
            user_state['report_text'] = report_text

        # Обрабатываем вложения
        attachments = user_state.get('report_attachments', [])
        if message.photo:
            photo = message.photo[-1]
            attachments.append({'type': 'photo', 'file_id': photo.file_id})
        elif message.document:
            attachments.append({
                'type': 'document', 
                'file_id': message.document.file_id, 
                'file_name': message.document.file_name
            })

        if message.photo or message.document:
            user_state['report_attachments'] = attachments
            set_user_state(chat_id, user_state)
            
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("✅ Завершить и отправить", callback_data="finish_report"))
            markup.add(InlineKeyboardButton("🗑️ Сбросить вложения", callback_data="clear_report_attachments"))
            
            status_msg = f"✅ Вложение добавлено (всего: {len(attachments)})."
            if report_text:
                status_msg += f"\n📝 Текст отчета: {report_text[:50]}..."
            
            bot.send_message(chat_id, f"{status_msg}\nВы можете отправить еще или завершить:", reply_markup=markup)
            return

        # Проверяем, что есть либо достаточный текст, либо вложения
        if len(report_text) < 10 and not attachments:
            bot.send_message(message.chat.id, "❌ Отчет должен содержать минимум 10 символов текста ИЛИ вложения (фото/файлы)")
            return

        # Если это текст, и мы не в процессе сбора вложений (или решили отправить текст)
        active_task.report_text = report_text
        active_task.report_attachments = attachments
        active_task.status = 'pending_review'
        active_task.save()

        # Уведомляем создателя
        notify_creator_about_report(active_task)

        clear_user_state(chat_id)
        bot.send_message(message.chat.id, "✅ Отчет успешно отправлен создателю для проверки", reply_markup=TASK_MANAGEMENT_MARKUP)

    except Exception as e:
        logger.error(f"Ошибка при отправке отчета: {e}")
        bot.send_message(message.chat.id, f"❌ Ошибка при отправке отчета: {e}")


def finish_report_callback(call: CallbackQuery) -> None:
    chat_id = get_chat_id_from_update(call)
    user_state = get_user_state(chat_id)
    
    if not user_state or user_state.get('state') != 'waiting_report':
        bot.answer_callback_query(call.id, "Ошибка состояния")
        return

    task_id = user_state.get('report_task_id')
    attachments = user_state.get('report_attachments', [])
    
    try:
        task = Task.objects.get(id=task_id)
        report_text = user_state.get('report_text')
        
        if not report_text:
            report_text = f"Отчет с вложениями ({len(attachments)} шт.)"
        
        task.report_text = report_text
        task.report_attachments = attachments
        task.status = 'pending_review'
        task.save()
        
        notify_creator_about_report(task)
        
        clear_user_state(chat_id)
        bot.edit_message_text("✅ Отчет успешно отправлен!", chat_id, call.message.message_id)
        bot.send_message(chat_id, "Вы вернулись в главное меню", reply_markup=TASK_MANAGEMENT_MARKUP)
        
    except Exception as e:
        logger.error(f"Error finishing report: {e}")
        bot.answer_callback_query(call.id, "Ошибка при сохранении")


def notify_creator_about_report(task: Task) -> None:
    try:
        creator_text = f"📬 **Ваша задача готова к проверке**\n\n{format_task_info(task)}\n\n"
        if task.report_text:
            creator_text += f"📄 Отчет исполнителя:\n{task.report_text}\n"

        markup = get_task_actions_markup(task.id, task.status, task.report_attachments, True, False)
        bot.send_message(task.creator.telegram_id, creator_text, reply_markup=markup, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Не удалось уведомить создателя: {e}")


def notify_creator_about_comment(task: Task, comment: TaskComment) -> None:
    """
    Уведомляет создателя задачи о новом комментарии
    """
    try:
        notification_text = f"💬 **Новый комментарий к задаче**\n\n"
        notification_text += f"📋 Задача: {task.title}\n"
        notification_text += f"👤 Автор комментария: {comment.author.user_name}\n"
        notification_text += f"💭 Комментарий: {comment.text}\n"

        markup = get_task_actions_markup(task.id, task.status, task.report_attachments, 
                                        True, False)
        bot.send_message(task.creator.telegram_id, notification_text, 
                        reply_markup=markup, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Не удалось уведомить создателя о комментарии: {e}")


def initiate_comment(chat_id: str, task_id: int) -> None:
    user_state = get_user_state(chat_id) or {}
    user_state['state'] = 'waiting_comment'
    user_state['comment_task_id'] = task_id
    set_user_state(chat_id, user_state)
    
    bot.send_message(chat_id, "📝 Введите ваш комментарий к задаче:", 
                     reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("⬅️ Отмена", callback_data=f"task_progress_{task_id}")))


def handle_task_comment(message: Message) -> None:
    chat_id = str(message.chat.id)
    user_state = get_user_state(chat_id)
    
    if not user_state or user_state.get('state') != 'waiting_comment':
        return
        
    task_id = user_state.get('comment_task_id')
    if not task_id or not message.text:
        return

    try:
        task = Task.objects.get(id=task_id)
        user = get_or_create_user(chat_id)
        
        comment = TaskComment.objects.create(
            task=task,
            author=user,
            text=message.text.strip()
        )
        
        bot.send_message(chat_id, "✅ Комментарий добавлен!")
        clear_user_state(chat_id)
        
        # Уведомляем создателя задачи, если комментарий оставил не он сам
        if task.creator.telegram_id != user.telegram_id:
            notify_creator_about_comment(task, comment)
        
        # Показываем задачу снова
        is_creator = task.creator.telegram_id == user.telegram_id
        is_assignee = task.assignee.telegram_id == user.telegram_id
        show_task_progress(chat_id, task, is_creator, is_assignee)
        
    except Exception as e:
        logger.error(f"Error adding comment: {e}")
        bot.send_message(chat_id, "❌ Ошибка при добавлении комментария")


def view_report_attachments_callback(call: CallbackQuery) -> None:
    # (Existing logic, keep it)
    try:
        task_id = int(call.data.split('_')[3])
        task = Task.objects.get(id=task_id)
        chat_id = get_chat_id_from_update(call)
        allowed, error_msg = check_permissions(chat_id, task, require_creator=False)
        if not allowed:
            bot.answer_callback_query(call.id, error_msg, show_alert=True)
            return

        if not task.report_attachments:
            bot.answer_callback_query(call.id, "Нет вложений в отчете", show_alert=True)
            return

        bot.answer_callback_query(call.id, "Отправляю вложения...")
        for attachment in task.report_attachments:
            try:
                if attachment['type'] == 'photo':
                    bot.send_photo(call.message.chat.id, attachment['file_id'])
                elif attachment['type'] == 'document':
                    bot.send_document(call.message.chat.id, attachment['file_id'])
            except Exception as e:
                logger.error(f"Ошибка при отправке вложения: {e}")

    except (ValueError, ObjectDoesNotExist):
        bot.answer_callback_query(call.id, "Задача не найдена", show_alert=True)

def task_comment_callback(call: CallbackQuery) -> None:
    try:
        task_id = int(call.data.split('_')[2])
        chat_id = str(call.message.chat.id)
        initiate_comment(chat_id, task_id)
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Error in task_comment_callback: {e}")

def clear_report_attachments_callback(call: CallbackQuery) -> None:
    chat_id = str(call.message.chat.id)
    user_state = get_user_state(chat_id)
    if user_state and user_state.get('state') == 'waiting_report':
        user_state['report_attachments'] = []
        user_state['report_text'] = ''
        set_user_state(chat_id, user_state)
        bot.answer_callback_query(call.id, "Отчет очищен")
        bot.edit_message_text("❌ Данные отчета очищены. Отправьте новые или напишите текст отчета:", chat_id, call.message.message_id)
