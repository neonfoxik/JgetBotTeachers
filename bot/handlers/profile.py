from bot.handlers.utils import (
    get_or_create_user, get_user_state, set_user_state, clear_user_state, check_registration
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
⏰ Время работы: с {user.work_start} до {user.work_end}
{'👑 Статус: Администратор' if user.is_admin else ''}
"""
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("✏️ Изменить инфо о себе", callback_data="profile_edit_info_menu"))
        markup.add(InlineKeyboardButton("⏰ Редактировать время работы", callback_data="profile_edit_work_hours"))
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
    if not check_registration(call):
        return
    chat_id = str(call.message.chat.id)
    show_profile(chat_id, call.message.message_id)
    bot.answer_callback_query(call.id)


def profile_edit_info_menu_callback(call: CallbackQuery) -> None:
    """Меню выбора, что именно изменить в инфо о себе"""
    chat_id = str(call.message.chat.id)
    text = "📝 Что вы хотите изменить?"
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📝 Изменить имя", callback_data="profile_edit_first_name"))
    markup.add(InlineKeyboardButton("📝 Изменить фамилию", callback_data="profile_edit_last_name"))
    markup.add(InlineKeyboardButton("⬅️ Назад", callback_data="profile"))
    
    bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=markup)
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
            InlineKeyboardButton("⬅️ Отмена", callback_data="profile_edit_info_menu")
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
            InlineKeyboardButton("⬅️ Отмена", callback_data="profile_edit_info_menu")
        )
    )
    bot.answer_callback_query(call.id)


def profile_edit_work_hours_callback(call: CallbackQuery) -> None:
    """Начинает процесс изменения рабочего времени"""
    chat_id = str(call.message.chat.id)
    user_state = get_user_state(chat_id) or {}
    user_state['state'] = 'waiting_work_hours'
    if 'work_start_temp' in user_state:
        del user_state['work_start_temp']
    set_user_state(chat_id, user_state)
    
    user = User.objects.get(telegram_id=chat_id)
    
    text = f"""⏰ **РЕДАКТИРОВАНИЕ ВРЕМЕНИ РАБОТЫ**

Текущее время: с {user.work_start} до {user.work_end}

Введите новое время работы в формате: `с 7 до 23` или `7-23`
(только часы, без минут)"""
    
    bot.edit_message_text(
        text,
        chat_id,
        call.message.message_id,
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("⬅️ Отмена", callback_data="profile")
        ),
        parse_mode='Markdown'
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
    elif state == 'waiting_work_hours':
        handle_work_hours_input(message, chat_id)


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
        bot.send_message(chat_id, "➡️ Имя успешно обновлено!")
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
        bot.send_message(chat_id, "➡️ Фамилия успешно обновлена!")
        show_profile(chat_id)
        
    except Exception as e:
        logger.error(f"Error updating last name: {e}")
        bot.send_message(chat_id, "❌ Ошибка при обновлении фамилии")


def handle_work_hours_input(message: Message, chat_id: str) -> None:
    """Обрабатывает ввод рабочего времени"""
    import re
    text = message.text.lower().strip()
    user_state = get_user_state(chat_id) or {}
    
    # Пытаемся найти все числа во вводе
    nums = re.findall(r'\d+', text)
    
    start, end = None, None
    
    if len(nums) >= 2:
        # Форматы типа "7-21", "7 21", "с 7 до 21"
        start, end = map(int, nums[:2])
    elif len(nums) == 1:
        # Формат типа "7", а потом "21" в другом сообщении
        val = int(nums[0])
        if 0 <= val <= 24:
            if 'work_start_temp' in user_state:
                start = user_state['work_start_temp']
                end = val
                # Очистим временную переменную позже при успешном сохранении
            else:
                user_state['work_start_temp'] = val
                set_user_state(chat_id, user_state)
                bot.send_message(chat_id, f"⏰ Начало работы установлено: {val}:00. Введите время окончания (второе число):")
                return
        else:
            bot.send_message(chat_id, "❌ Часы должны быть в диапазоне от 0 до 24")
            return
    
    if start is None or end is None or not (0 <= start <= 24) or not (0 <= end <= 24):
        bot.send_message(chat_id, "❌ Неверный формат. Используйте: `7-21`, `7 21` или введите числа по очереди.", parse_mode='Markdown')
        return
    
    try:
        user = User.objects.get(telegram_id=chat_id)
        user.work_start = start
        user.work_end = end
        user.save()
        
        # Удаляем временные данные
        if 'work_start_temp' in user_state:
            del user_state['work_start_temp']
        
        user_state['state'] = '' # Очищаем состояние
        set_user_state(chat_id, user_state)
        
        bot.send_message(chat_id, f"➡️ Время работы успешно обновлено: с {start}:00 до {end}:00!")
        show_profile(chat_id)
        
    except Exception as e:
        logger.error(f"Error updating work hours: {e}")
        bot.send_message(chat_id, "❌ Ошибка при обновлении времени работы")
