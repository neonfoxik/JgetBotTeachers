from bot.handlers.utils import (
    get_or_create_user, safe_edit_or_send_message, set_user_state, get_user_state, clear_user_state
)
from bot import bot, logger
from bot.keyboards import main_markup, TASK_MANAGEMENT_MARKUP
from telebot.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

def start_tutorial(chat_id: str, message_id: int = None) -> None:
    text = """🎓 ДОБРО ПОЖАЛОВАТЬ В ОБУЧЕНИЕ!

Я помогу тебе освоиться. Давай создадим твою первую задачу и выполним её.

Шаг 1: Нажми кнопку "➕ Создать задачу" ниже."""
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("➕ Создать задачу", callback_data="create_task"))
    
    set_user_state(chat_id, {'state': 'tutorial_waiting_for_creation'})
    
    if message_id:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=markup)
    else:
        bot.send_message(chat_id, text, reply_markup=markup)

def tutorial_task_created(chat_id: str, task_id: int) -> None:
    text = f"""✅ Отлично! Первая задача создана.

Теперь давай её выполним. Это самый важный этап!

Шаг 2: Нажми на кнопку "📋 Посмотреть задачу", а затем выбери "✅ Отметить выполненной"."""
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📋 Посмотреть задачу", callback_data=f"task_progress_{task_id}"))
    
    set_user_state(chat_id, {
        'state': 'tutorial_waiting_for_completion',
        'tutorial_task_id': task_id
    })
    
    bot.send_message(chat_id, text, reply_markup=markup)

def finish_tutorial(chat_id: str) -> None:
    text = """🎉 ПОЗДРАВЛЯЮ!

Ты прошел краткий курс обучения. Теперь ты умеешь:
✅ Создавать задачи
✅ Назначать их (в туториале ты назначил её себе)
✅ Отмечать выполнение

Удачи в работе! Используй главное меню для управления задачами."""
    
    clear_user_state(chat_id)
    bot.send_message(chat_id, text, reply_markup=TASK_MANAGEMENT_MARKUP)

def start_tutorial_callback(call: CallbackQuery) -> None:
    chat_id = str(call.message.chat.id)
    start_tutorial(chat_id, call.message.message_id)
