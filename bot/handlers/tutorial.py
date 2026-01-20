from bot.handlers.utils import (
    get_or_create_user, safe_edit_or_send_message, set_user_state, get_user_state, clear_user_state
)
from bot import bot, logger
from bot.keyboards import main_markup, TASK_MANAGEMENT_MARKUP
from telebot.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

def start_tutorial(chat_id: str, message_id: int = None) -> None:
    text = """👋 **Привет! Я — твой личный помощник по задачам.**

Давай я быстро научу тебя основам. Работа в боте строится всего на трёх шагах:
1️⃣ **Создание**: пишем, что нужно сделать.
2️⃣ **Назначение**: выбираем, КТО это сделает.
3️⃣ **Выполнение**: отмечаем результат.

Начнём? Нажми кнопку ниже, чтобы создать твою первую задачу!"""
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🚀 Начать создание", callback_data="create_task"))
    
    set_user_state(chat_id, {
        'state': 'tutorial_waiting_for_creation',
        'tutorial_step': 'start'
    })
    
    if message_id:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode='Markdown')
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode='Markdown')

def tutorial_task_created(chat_id: str, task_id: int) -> None:
    text = f"""✨ **Ура! Твоя первая задача создана.**

Ты только что прошёл этапы ввода названия, описания и выбора исполнителя. 

Теперь самое важное — **контроль**. Давай посмотрим, как выглядит твоя задача "изнутри". Там ты сможешь управлять подзадачами или завершить её.

👇 Нажми на кнопку «Посмотреть задачу»:"""
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📋 Посмотреть задачу", callback_data=f"task_progress_{task_id}"))
    
    set_user_state(chat_id, {
        'state': 'tutorial_waiting_for_completion',
        'tutorial_task_id': task_id,
        'tutorial_step': 'view_task'
    })
    
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode='Markdown')

def finish_tutorial(chat_id: str) -> None:
    text = """🎉 **Поздравляю! Ты — мастер задач!**

Теперь ты знаешь всё необходимое:
✅ Как ставить задачи.
✅ Как следить за их выполнением.
✅ Как закрывать их.

Если возникнут вопросы — я всегда рядом. Удачи в делах! 🚀"""
    
    clear_user_state(chat_id)
    bot.send_message(chat_id, text, reply_markup=TASK_MANAGEMENT_MARKUP, parse_mode='Markdown')

def start_tutorial_callback(call: CallbackQuery) -> None:
    chat_id = str(call.message.chat.id)
    start_tutorial(chat_id, call.message.message_id)
