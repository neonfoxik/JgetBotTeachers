"""
Обработчики для работы с ролями при создании задач
"""
from bot.handlers.utils import (
    get_or_create_user, get_chat_id_from_update, safe_edit_or_send_message, get_user_state,
    set_user_state, clear_user_state
)
from bot import bot, logger
from bot.models import Role
from telebot.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton


def choose_role_from_list_callback(call: CallbackQuery) -> None:
    """Обработчик для кнопки 'Назначить роли' - показывает список всех ролей"""
    chat_id = get_chat_id_from_update(call)
    user_state = get_user_state(chat_id)
    if user_state:
        show_role_selection_list(chat_id, user_state, call)


def show_role_selection_list(chat_id: str, user_state: dict, call: CallbackQuery = None) -> None:
    """Показывает список всех ролей для выбора"""
    text = f"👥 Выберите роль для задачи '{user_state.get('title', '')}'\n\n"
    text += "Все пользователи с выбранной ролью получат доступ к этой задаче:"
    
    roles = list(Role.objects.all())
    
    if not roles:
        text = "❌ В системе пока нет ролей. Создайте роли через админ-панель."
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_assignee_selection"))
        if call:
            safe_edit_or_send_message(chat_id, text, reply_markup=markup, message_id=call.message.message_id)
        else:
            bot.send_message(chat_id, text, reply_markup=markup)
        return
    
    markup = InlineKeyboardMarkup()
    for role in roles:
        users_count = role.users.count()
        button_text = f"{role.name} ({users_count} польз.)"
        markup.add(InlineKeyboardButton(button_text, callback_data=f"select_role_{role.id}"))
    
    markup.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_assignee_selection"))
    
    if call:
        safe_edit_or_send_message(chat_id, text, reply_markup=markup, message_id=call.message.message_id, parse_mode='Markdown')
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode='Markdown')


def select_role_callback(call: CallbackQuery) -> None:
    """Обработчик выбора роли для задачи"""
    try:
        from bot.handlers.task_creation import create_task_from_state
        
        role_id = int(call.data.split('_')[2])
        chat_id = get_chat_id_from_update(call)
        user_state = get_user_state(chat_id)

        if user_state:
            role = Role.objects.get(id=role_id)
            user_state['assigned_role_id'] = role_id
            user_state['assignee_id'] = None  # Очищаем assignee_id, так как назначаем роли
            set_user_state(chat_id, user_state)

            success, msg, markup = create_task_from_state(chat_id, user_state, call.message.message_id)
            
            # Очищаем состояние только при успехе и если это не туториал
            if success:
                if user_state.get('state') != 'tutorial_waiting_for_creation' and not user_state.get('is_tutorial'):
                    clear_user_state(chat_id)
                
            safe_edit_or_send_message(call.message.chat.id, msg, reply_markup=markup, message_id=call.message.message_id, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Ошибка при выборе роли: {e}")
        bot.answer_callback_query(call.id, "Ошибка при выборе роли", show_alert=True)
