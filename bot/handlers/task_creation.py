from bot.handlers.utils import (
    get_or_create_user, get_chat_id_from_update, safe_edit_or_send_message, get_user_state,
    set_user_state, clear_user_state, check_permissions, format_task_info
)
from bot import bot, logger
from bot.models import User, Task
from bot.keyboards import (
    get_user_selection_markup, TASK_MANAGEMENT_MARKUP
)
from telebot.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from datetime import datetime
from django.utils import timezone


def show_assignee_selection_menu(chat_id: str, user_state: dict, call: CallbackQuery = None) -> None:
    text = f"👤 Выберите исполнителя для задачи '{user_state.get('title', '')}'\n\n"
    text += "Выберите пользователя из списка или пропустите, чтобы назначить себе:"

    users = list(User.objects.all())
    markup = get_user_selection_markup(users)

    if call:
        safe_edit_or_send_message(chat_id, text, reply_markup=markup, message_id=call.message.message_id)
    else:
        bot.send_message(chat_id, text, reply_markup=markup)


def create_task_from_state(chat_id: str, user_state: dict) -> tuple[bool, str, InlineKeyboardMarkup]:
    try:
        creator = get_or_create_user(chat_id)
        assignee_id = user_state.get('assignee_id')
        if assignee_id:
            assignee = User.objects.get(telegram_id=assignee_id)
        else:
            assignee = creator

        with transaction.atomic():
            task = Task.objects.create(
                title=user_state['title'],
                description=user_state['description'],
                creator=creator,
                assignee=assignee,
                due_date=user_state.get('due_date'),
            )

            success_msg = f"✅ Задача '{task.title}' успешно создана!\n\n"
            success_msg += f"👤 Исполнитель: {assignee.user_name}\n"
            if task.due_date:
                success_msg += f"⏰ Срок: {task.due_date.strftime('%d.%m.%Y %H:%M')}"

            return True, success_msg, TASK_MANAGEMENT_MARKUP

    except Exception as e:
        logger.error(f"Ошибка при создании задачи: {e}")
        return False, f"❌ Ошибка при создании задачи: {str(e)}", TASK_MANAGEMENT_MARKUP


def handle_task_creation_messages(message: Message) -> None:
    chat_id = str(message.chat.id)
    logger.info(f"Получено сообщение от {chat_id}: '{message.text}'")
    
    try:
        user_state = get_user_state(chat_id)
        logger.info(f"Состояние пользователя {chat_id}: {user_state}")
        
        # Проверяем, есть ли состояние и оно связано с созданием задачи
        if not user_state or not user_state.get('state'):
            logger.info(f"Нет активного состояния создания задачи для пользователя {chat_id}")
            return
        
        state = user_state.get('state')
        logger.info(f"Текущее состояние: {state}")
        
        # Проверяем, что состояние относится к созданию задачи
        if state not in ['waiting_task_title', 'waiting_task_description', 'waiting_due_date']:
            logger.info(f"Состояние {state} не относится к созданию задачи, пропускаем")
            return

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
    
    except Exception as e:
        logger.error(f"Ошибка при обработке сообщения создания задачи для {chat_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        bot.send_message(chat_id, "❌ Произошла ошибка при обработке сообщения. Попробуйте начать создание задачи заново.")


def skip_description_callback(call: CallbackQuery) -> None:
    chat_id = get_chat_id_from_update(call)
    user_state = get_user_state(chat_id)
    if user_state:
        user_state['description'] = None
        user_state['state'] = 'waiting_due_date'
        set_user_state(chat_id, user_state)
        text = f"📅 Введите срок выполнения задачи в формате ДД.ММ.ГГГГ ЧЧ:ММ\n\nТекущее описание: не указано"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Без срока", callback_data="skip_due_date"))
        markup.add(InlineKeyboardButton("⬅️ Отмена", callback_data="cancel_task_creation"))
        safe_edit_or_send_message(call.message.chat.id, text, reply_markup=markup, message_id=call.message.message_id)


def skip_due_date_callback(call: CallbackQuery) -> None:
    chat_id = get_chat_id_from_update(call)
    user_state = get_user_state(chat_id)
    if user_state:
        user_state['due_date'] = None
        user_state['state'] = 'waiting_assignee_selection'
        set_user_state(chat_id, user_state)
        show_assignee_selection_menu(chat_id, user_state, call)


def assign_to_creator_callback(call: CallbackQuery) -> None:
    chat_id = get_chat_id_from_update(call)
    user_state = get_user_state(chat_id)
    if user_state:
        user_state['assignee_id'] = None  # None означает назначить себе
        set_user_state(chat_id, user_state)

        success, msg, markup = create_task_from_state(chat_id, user_state)
        clear_user_state(chat_id)
        safe_edit_or_send_message(call.message.chat.id, msg, reply_markup=markup, message_id=call.message.message_id)


def skip_assignee_callback(call: CallbackQuery) -> None:
    # То же самое что и assign_to_creator
    assign_to_creator_callback(call)


def choose_assignee_callback(call: CallbackQuery) -> None:
    chat_id = get_chat_id_from_update(call)
    user_state = get_user_state(chat_id)
    if user_state:
        show_assignee_selection_menu(chat_id, user_state, call)


def user_page_callback(call: CallbackQuery) -> None:
    try:
        page = int(call.data.split('_')[2])
        show_user_selection_page(call, page)
    except (ValueError, IndexError):
        bot.answer_callback_query(call.id, "Ошибка навигации", show_alert=True)


def show_user_selection_page(call: CallbackQuery, page: int, users_per_page: int = 5) -> None:
    users = list(User.objects.all())
    markup = get_user_selection_markup(users, page, users_per_page)
    text = f"👤 Выберите исполнителя (страница {page + 1}):"
    safe_edit_or_send_message(call.message.chat.id, text, reply_markup=markup, message_id=call.message.message_id)


def select_user_callback(call: CallbackQuery) -> None:
    try:
        assignee_telegram_id = call.data.split('_')[2]
        chat_id = get_chat_id_from_update(call)
        user_state = get_user_state(chat_id)

        if user_state:
            user_state['assignee_id'] = assignee_telegram_id
            set_user_state(chat_id, user_state)

            success, msg, markup = create_task_from_state(chat_id, user_state)
            clear_user_state(chat_id)
            safe_edit_or_send_message(call.message.chat.id, msg, reply_markup=markup, message_id=call.message.message_id)

    except Exception as e:
        logger.error(f"Ошибка при выборе пользователя: {e}")
        bot.answer_callback_query(call.id, "Ошибка при выборе пользователя", show_alert=True)


def back_to_assignee_selection_callback(call: CallbackQuery) -> None:
    chat_id = get_chat_id_from_update(call)
    user_state = get_user_state(chat_id)
    if user_state:
        show_assignee_selection_menu(chat_id, user_state, call)


def back_to_assignee_type_callback(call: CallbackQuery) -> None:
    chat_id = get_chat_id_from_update(call)
    user_state = get_user_state(chat_id)
    if user_state:
        show_assignee_selection_menu(chat_id, user_state, call)


def cancel_task_creation_callback(call: CallbackQuery) -> None:
    clear_user_state(str(call.message.chat.id))
    text = "❌ Создание задачи отменено"
    safe_edit_or_send_message(call.message.chat.id, text, reply_markup=TASK_MANAGEMENT_MARKUP, message_id=call.message.message_id)
