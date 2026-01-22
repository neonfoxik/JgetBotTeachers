from bot.handlers.utils import get_user_state, set_user_state, clear_user_state
from bot import bot, logger
from bot.models import User
from telebot.types import Message, InlineKeyboardMarkup, InlineKeyboardButton


def start_registration(chat_id: str, telegram_username: str = None, telegram_first_name: str = None) -> None:
    """Начинает процесс регистрации нового пользователя"""
    user_state = {
        'state': 'registration_waiting_first_name',
        'telegram_username': telegram_username or chat_id,
        'telegram_first_name': telegram_first_name or ""
    }
    set_user_state(chat_id, user_state)
    
    welcome_text = """👋 Добро пожаловать!

Для начала работы с ботом, пожалуйста, укажите ваши данные.

✏️ Введите ваше имя:"""
    
    bot.send_message(chat_id, welcome_text)


def handle_registration_input(message: Message) -> bool:
    """
    Обрабатывает ввод данных при регистрации
    Возвращает True, если сообщение было обработано
    """
    chat_id = str(message.chat.id)
    user_state = get_user_state(chat_id)
    
    if not user_state:
        return False
    
    state = user_state.get('state')
    
    if state == 'registration_waiting_first_name':
        handle_registration_first_name(message, chat_id, user_state)
        return True
    elif state == 'registration_waiting_last_name':
        handle_registration_last_name(message, chat_id, user_state)
        return True
    
    return False


def handle_registration_first_name(message: Message, chat_id: str, user_state: dict) -> None:
    """Обрабатывает ввод имени при регистрации"""
    if not message.text or len(message.text.strip()) < 2:
        bot.send_message(chat_id, "❌ Имя должно содержать минимум 2 символа. Попробуйте еще раз:")
        return
    
    # Сохраняем имя и переходим к запросу фамилии
    user_state['first_name'] = message.text.strip()
    user_state['state'] = 'registration_waiting_last_name'
    set_user_state(chat_id, user_state)
    
    bot.send_message(chat_id, "✅ Отлично!\n\n✏️ Теперь введите вашу фамилию:")


def handle_registration_last_name(message: Message, chat_id: str, user_state: dict) -> None:
    """Обрабатывает ввод фамилии при регистрации и завершает регистрацию"""
    if not message.text or len(message.text.strip()) < 2:
        bot.send_message(chat_id, "❌ Фамилия должна содержать минимум 2 символа. Попробуйте еще раз:")
        return
    
    # Создаем пользователя с полными данными
    try:
        user = User.objects.create(
            telegram_id=chat_id,
            user_name=user_state.get('telegram_username', chat_id),
            first_name=user_state.get('first_name', ''),
            last_name=message.text.strip(),
            is_admin=False
        )
        
        clear_user_state(chat_id)
        
        # Показываем приветственное сообщение с меню
        show_welcome_menu(chat_id, user)
        
    except Exception as e:
        logger.error(f"Error creating user during registration: {e}")
        bot.send_message(chat_id, "❌ Ошибка при регистрации. Попробуйте команду /start еще раз")


def show_welcome_menu(chat_id: str, user: User) -> None:
    """Показывает приветственное меню после регистрации"""
    from bot.keyboards import get_main_menu
    
    welcome_text = f"""✅ Регистрация завершена!

👋 Привет, {user.get_full_name()}!

🤖 Я бот для управления задачами. Выберите действие:"""
    
    bot.send_message(chat_id, welcome_text, reply_markup=get_main_menu(user))
