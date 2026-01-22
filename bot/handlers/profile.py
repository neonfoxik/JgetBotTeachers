from bot.handlers.utils import (
    get_or_create_user, get_user_state, set_user_state, clear_user_state
)
from bot import bot, logger
from bot.models import User
from telebot.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton


def show_profile(chat_id: str, message_id: int = None) -> None:
    """Показывает профиль пользователя"""
    try:
        user = User.objects.get(telegram_id=chat_id)
        
        profile_text = f"""👤 **ВАШ ПРОФИЛЬ**

📝 Имя: {user.first_name or 'Не указано'}
📝 Фамилия: {user.last_name or 'Не указано'}
🆔 Username: @{user.user_name}
📅 Дата регистрации: {user.created_at.strftime('%d.%m.%Y')}
{'👑 Статус: Администратор' if user.is_admin else ''}
"""
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("✏️ Изменить имя", callback_data="profile_edit_first_name"))
        markup.add(InlineKeyboardButton("✏️ Изменить фамилию", callback_data="profile_edit_last_name"))
        markup.add(InlineKeyboardButton("⬅️ Главное меню", callback_data="main_menu"))
        
        if message_id:
            try:
                bot.edit_message_text(profile_text, chat_id, message_id, 
                                     reply_markup=markup, parse_mode='Markdown')
            except:
                bot.send_message(chat_id, profile_text, reply_markup=markup, parse_mode='Markdown')
        else:
            bot.send_message(chat_id, profile_text, reply_markup=markup, parse_mode='Markdown')
            
    except User.DoesNotExist:
        bot.send_message(chat_id, "❌ Пользователь не найден")
    except Exception as e:
        logger.error(f"Error showing profile: {e}")
        bot.send_message(chat_id, "❌ Ошибка при загрузке профиля")


def profile_callback(call: CallbackQuery) -> None:
    """Обработчик callback для профиля"""
    chat_id = str(call.message.chat.id)
    show_profile(chat_id, call.message.message_id)
    bot.answer_callback_query(call.id)


def profile_edit_first_name_callback(call: CallbackQuery) -> None:
    """Начинает процесс изменения имени"""
    chat_id = str(call.message.chat.id)
    user_state = get_user_state(chat_id) or {}
    user_state['state'] = 'waiting_first_name'
    set_user_state(chat_id, user_state)
    
    bot.edit_message_text(
        "✏️ Введите ваше имя:",
        chat_id,
        call.message.message_id,
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("⬅️ Отмена", callback_data="profile")
        )
    )
    bot.answer_callback_query(call.id)


def profile_edit_last_name_callback(call: CallbackQuery) -> None:
    """Начинает процесс изменения фамилии"""
    chat_id = str(call.message.chat.id)
    user_state = get_user_state(chat_id) or {}
    user_state['state'] = 'waiting_last_name'
    set_user_state(chat_id, user_state)
    
    bot.edit_message_text(
        "✏️ Введите вашу фамилию:",
        chat_id,
        call.message.message_id,
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("⬅️ Отмена", callback_data="profile")
        )
    )
    bot.answer_callback_query(call.id)


def handle_profile_input(message: Message) -> None:
    """Обрабатывает ввод данных профиля"""
    chat_id = str(message.chat.id)
    user_state = get_user_state(chat_id)
    
    if not user_state:
        return
    
    state = user_state.get('state')
    
    if state == 'waiting_first_name':
        handle_first_name_input(message, chat_id)
    elif state == 'waiting_last_name':
        handle_last_name_input(message, chat_id)


def handle_first_name_input(message: Message, chat_id: str) -> None:
    """Обрабатывает ввод имени"""
    if not message.text or len(message.text.strip()) < 2:
        bot.send_message(chat_id, "❌ Имя должно содержать минимум 2 символа")
        return
    
    try:
        user = User.objects.get(telegram_id=chat_id)
        user.first_name = message.text.strip()
        user.save()
        
        clear_user_state(chat_id)
        bot.send_message(chat_id, "✅ Имя успешно обновлено!")
        show_profile(chat_id)
        
    except Exception as e:
        logger.error(f"Error updating first name: {e}")
        bot.send_message(chat_id, "❌ Ошибка при обновлении имени")


def handle_last_name_input(message: Message, chat_id: str) -> None:
    """Обрабатывает ввод фамилии"""
    if not message.text or len(message.text.strip()) < 2:
        bot.send_message(chat_id, "❌ Фамилия должна содержать минимум 2 символа")
        return
    
    try:
        user = User.objects.get(telegram_id=chat_id)
        user.last_name = message.text.strip()
        user.save()
        
        clear_user_state(chat_id)
        bot.send_message(chat_id, "✅ Фамилия успешно обновлена!")
        show_profile(chat_id)
        
    except Exception as e:
        logger.error(f"Error updating last name: {e}")
        bot.send_message(chat_id, "❌ Ошибка при обновлении фамилии")
