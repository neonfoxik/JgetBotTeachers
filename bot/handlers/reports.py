from bot.handlers.utils import (
    get_or_create_user, get_chat_id_from_update, safe_edit_or_send_message, format_task_info,
    check_permissions
)
from bot.handlers.main import show_task_progress
from bot import bot, logger
from bot.models import User, Task
from bot.keyboards import (
    get_task_actions_markup, TASK_MANAGEMENT_MARKUP
)
from telebot.types import Message
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone


def initiate_task_close(chat_id: str, task: Task) -> None:
    """Инициирует процесс закрытия задачи с отправкой отчета"""
    text = f"📄 ОТПРАВКА ОТЧЕТА ПО ЗАДАЧЕ\n\n{format_task_info(task)}\n\n"
    text += "Опишите что было сделано (минимум 10 символов) или прикрепите фото/файлы:"

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📎 Прикрепить файлы", callback_data=f"attach_files_{task.id}"))
    markup.add(InlineKeyboardButton("⬅️ Отмена", callback_data=f"task_progress_{task.id}"))

    bot.send_message(chat_id, text, reply_markup=markup)


@bot.message_handler(content_types=['text', 'photo', 'document'])
def handle_task_report(message: Message) -> None:
    chat_id = str(message.chat.id)
    user = get_or_create_user(chat_id)

    # Проверяем, есть ли активная задача для отправки отчета
    try:
        # Ищем активную задачу пользователя
        active_task = Task.objects.filter(
            assignee=user,
            status='active'
        ).first()

        if not active_task:
            return  # Игнорируем сообщение, если нет активной задачи

        # Проверяем права
        allowed, error_msg = check_permissions(chat_id, active_task, require_creator=False)
        if not allowed:
            return

        # Обрабатываем текстовый отчет
        if message.text and not message.text.startswith('/'):
            report_text = message.text.strip()
            if len(report_text) < 10:
                bot.send_message(message.chat.id, "❌ Отчет должен содержать минимум 10 символов текста ИЛИ вложения (фото/файлы)")
                return

            active_task.report_text = report_text

        # Обрабатываем вложения
        attachments = []
        if message.photo:
            # Получаем самое большое фото
            photo = message.photo[-1]
            file_info = bot.get_file(photo.file_id)
            attachments.append({
                'type': 'photo',
                'file_id': photo.file_id,
                'file_path': file_info.file_path
            })

        if message.document:
            file_info = bot.get_file(message.document.file_id)
            attachments.append({
                'type': 'document',
                'file_id': message.document.file_id,
                'file_name': message.document.file_name,
                'file_path': file_info.file_path
            })

        # Сохраняем отчет и вложения
        if message.text or attachments:
            active_task.report_attachments = attachments
            active_task.status = 'pending_review'
            active_task.save()

            # Уведомляем создателя
            try:
                creator_text = f"📬 ВАША ЗАДАЧА ГОТОВА К ПРОВЕРКЕ\n\n{format_task_info(active_task)}\n\n"
                if active_task.report_text:
                    creator_text += f"📄 Отчет исполнителя:\n{active_task.report_text}\n"

                markup = get_task_actions_markup(active_task.id, active_task.status, active_task.report_attachments, True, False)
                bot.send_message(active_task.creator.telegram_id, creator_text, reply_markup=markup)

                # Отправляем вложения создателю
                for attachment in attachments:
                    if attachment['type'] == 'photo':
                        bot.send_photo(active_task.creator.telegram_id, attachment['file_id'])
                    elif attachment['type'] == 'document':
                        bot.send_document(active_task.creator.telegram_id, attachment['file_id'])

            except Exception as e:
                logger.error(f"Не удалось уведомить создателя: {e}")
                bot.send_message(message.chat.id, f"⚠️ Не удалось уведомить создателя: {e}")

            bot.send_message(message.chat.id, "✅ Отчет успешно отправлен создателю для проверки", reply_markup=TASK_MANAGEMENT_MARKUP)

        else:
            bot.send_message(message.chat.id, "❌ Отчет должен содержать минимум 10 символов текста ИЛИ вложения (фото/файлы)")

    except Exception as e:
        logger.error(f"Ошибка при отправке отчета: {e}")
        bot.send_message(message.chat.id, f"❌ Ошибка при отправке отчета: {e}")


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
            bot.answer_callback_query(call.id, "Нет вложений в отчете", show_alert=True)
            return

        # Отправляем все вложения
        for attachment in task.report_attachments:
            try:
                if attachment['type'] == 'photo':
                    bot.send_photo(call.message.chat.id, attachment['file_id'])
                elif attachment['type'] == 'document':
                    bot.send_document(call.message.chat.id, attachment['file_id'])
            except Exception as e:
                logger.error(f"Ошибка при отправке вложения: {e}")

        bot.answer_callback_query(call.id, f"Отправлено {len(task.report_attachments)} вложений")

    except (ValueError, ObjectDoesNotExist):
        bot.answer_callback_query(call.id, "Задача не найдена", show_alert=True)
