from datetime import datetime, timedelta
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from django.utils import timezone
from bot import bot, logger


def create_calendar(year: int = None, month: int = None) -> tuple[str, InlineKeyboardMarkup]:
    """
    Создает календарь для выбора даты
    """
    now = timezone.now()
    if year is None:
        year = now.year
    if month is None:
        month = now.month

    # Создаем календарь
    markup = InlineKeyboardMarkup(row_width=7)

    # Заголовок с месяцем и годом
    month_names = [
        "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
        "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
    ]

    # Кнопки навигации
    nav_row = []
    if month > 1:
        nav_row.append(InlineKeyboardButton("◀️", callback_data=f"calendar_prev_{year}_{month}"))
    else:
        nav_row.append(InlineKeyboardButton("◀️", callback_data=f"calendar_prev_{year-1}_{12}"))

    nav_row.append(InlineKeyboardButton(f"{month_names[month-1]} {year}", callback_data="calendar_ignore"))

    if month < 12:
        nav_row.append(InlineKeyboardButton("▶️", callback_data=f"calendar_next_{year}_{month}"))
    else:
        nav_row.append(InlineKeyboardButton("▶️", callback_data=f"calendar_next_{year+1}_{1}"))

    markup.row(*nav_row)

    # Дни недели
    week_days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    markup.row(*[InlineKeyboardButton(day, callback_data="calendar_ignore") for day in week_days])

    # Получаем первый день месяца
    first_day = datetime(year, month, 1)
    # Получаем день недели первого дня (0=понедельник)
    start_weekday = (first_day.weekday() + 1) % 7

    # Получаем количество дней в месяце
    if month == 12:
        last_day = datetime(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = datetime(year, month + 1, 1) - timedelta(days=1)
    days_in_month = last_day.day

    # Создаем сетку дней
    current_row = []
    day_counter = 1

    # Пустые ячейки до первого дня месяца
    for _ in range(start_weekday):
        current_row.append(InlineKeyboardButton(" ", callback_data="calendar_ignore"))

    # Заполняем дни месяца
    for day in range(1, days_in_month + 1):
        current_date = datetime(year, month, day)
        today = now.date()

        # Проверяем, является ли день сегодняшним или прошедшим
        if current_date.date() < today:
            # Прошедшие дни - неактивные
            current_row.append(InlineKeyboardButton(str(day), callback_data="calendar_ignore"))
        else:
            # Будущие дни - активные
            current_row.append(InlineKeyboardButton(str(day), callback_data=f"calendar_date_{year}_{month}_{day}"))

        # Если ряд заполнен, добавляем его в разметку
        if len(current_row) == 7:
            markup.row(*current_row)
            current_row = []

    # Добавляем оставшиеся дни, если ряд не полный
    if current_row:
        markup.row(*current_row)

    # Кнопки управления
    control_row = [
        InlineKeyboardButton("Без срока", callback_data="calendar_skip_date"),
        InlineKeyboardButton("⬅️ Отмена", callback_data="calendar_cancel")
    ]
    markup.row(*control_row)

    text = "📅 Выберите дату выполнения задачи:"

    return text, markup


def create_time_selector() -> tuple[str, InlineKeyboardMarkup]:
    """
    Создает селектор времени
    """
    markup = InlineKeyboardMarkup()

    # Предустановленные времена
    times = [
        ("09:00", "9_00"), ("10:00", "10_00"), ("11:00", "11_00"),
        ("12:00", "12_00"), ("13:00", "13_00"), ("14:00", "14_00"),
        ("15:00", "15_00"), ("16:00", "16_00"), ("17:00", "17_00"),
        ("18:00", "18_00"), ("19:00", "19_00"), ("20:00", "20_00")
    ]

    # Добавляем ряды по 4 кнопки
    for i in range(0, len(times), 4):
        row = []
        for time_text, time_data in times[i:i+4]:
            row.append(InlineKeyboardButton(time_text, callback_data=f"calendar_time_{time_data}"))
        markup.row(*row)

    # Дополнительные опции
    markup.row(
        InlineKeyboardButton("Без времени", callback_data="calendar_no_time"),
        InlineKeyboardButton("⬅️ Назад", callback_data="calendar_back_to_date")
    )

    text = "⏰ Выберите время выполнения задачи:"

    return text, markup


def process_calendar_callback(call, context: str = "task_creation") -> None:
    """
    Обрабатывает callback'и календаря
    context может быть "task_creation" или "task_editing_{task_id}"
    """
    data = call.data

    if data.startswith("calendar_prev_"):
        # Предыдущий месяц
        _, year, month = data.split("_")
        year, month = int(year), int(month)
        text, markup = create_calendar(year, month)
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif data.startswith("calendar_next_"):
        # Следующий месяц
        _, year, month = data.split("_")
        year, month = int(year), int(month)
        text, markup = create_calendar(year, month)
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif data.startswith("calendar_date_"):
        # Выбрана дата, показываем время
        _, year, month, day = data.split("_")
        year, month, day = int(year), int(month), int(day)

        # Сохраняем выбранную дату в состоянии пользователя
        from bot.handlers.utils import get_user_state, set_user_state
        chat_id = str(call.message.chat.id)
        user_state = get_user_state(chat_id)

        if user_state:
            user_state['selected_date'] = f"{year}-{month:02d}-{day:02d}"
            set_user_state(chat_id, user_state)

        text, markup = create_time_selector()
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif data.startswith("calendar_time_"):
        # Выбрано время, сохраняем полную дату и время
        _, hour, minute = data.split("_")
        hour, minute = int(hour), int(minute)

        from bot.handlers.utils import get_user_state, set_user_state
        chat_id = str(call.message.chat.id)
        user_state = get_user_state(chat_id)

        if user_state and 'selected_date' in user_state:
            date_str = user_state['selected_date']
            datetime_str = f"{date_str} {hour:02d}:{minute:02d}"
            due_date = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M')
            due_date = due_date.replace(tzinfo=timezone.get_current_timezone())

            # Сохраняем дату в зависимости от контекста
            if context.startswith("task_editing_"):
                task_id = context.split("_")[2]
                from bot.models import Task
                try:
                    task = Task.objects.get(id=int(task_id))
                    task.due_date = due_date
                    task.save()
                    text = f"✅ Срок задачи обновлен: {due_date.strftime('%d.%m.%Y %H:%M')}"
                    from bot.keyboards import get_task_actions_markup
                    markup = get_task_actions_markup(task.id, task.status, task.report_attachments,
                                                   task.creator.telegram_id == chat_id,
                                                   task.assignee.telegram_id == chat_id)
                except Exception as e:
                    logger.error(f"Ошибка при обновлении срока задачи: {e}")
                    text = "❌ Ошибка при обновлении срока задачи"
                    markup = None
            else:
                # Контекст создания задачи
                user_state['due_date'] = due_date
                user_state['state'] = 'waiting_assignee_selection'
                set_user_state(chat_id, user_state)

                from bot.handlers.task_creation import show_assignee_selection_menu
                show_assignee_selection_menu(chat_id, user_state, call)
                return  # Не отправляем сообщение, функция show_assignee_selection_menu сама обработает

            if markup:
                bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif data == "calendar_no_time":
        # Без времени - сохраняем только дату
        from bot.handlers.utils import get_user_state, set_user_state
        chat_id = str(call.message.chat.id)
        user_state = get_user_state(chat_id)

        if user_state and 'selected_date' in user_state:
            date_str = user_state['selected_date']
            due_date = datetime.strptime(date_str, '%Y-%m-%d')
            due_date = due_date.replace(tzinfo=timezone.get_current_timezone())

            if context.startswith("task_editing_"):
                task_id = context.split("_")[2]
                from bot.models import Task
                try:
                    task = Task.objects.get(id=int(task_id))
                    task.due_date = due_date
                    task.save()
                    text = f"✅ Срок задачи обновлен: {due_date.strftime('%d.%m.%Y')} (без времени)"
                    from bot.keyboards import get_task_actions_markup
                    markup = get_task_actions_markup(task.id, task.status, task.report_attachments,
                                                   task.creator.telegram_id == chat_id,
                                                   task.assignee.telegram_id == chat_id)
                except Exception as e:
                    logger.error(f"Ошибка при обновлении срока задачи: {e}")
                    text = "❌ Ошибка при обновлении срока задачи"
                    markup = None
            else:
                user_state['due_date'] = due_date
                user_state['state'] = 'waiting_assignee_selection'
                set_user_state(chat_id, user_state)

                from bot.handlers.task_creation import show_assignee_selection_menu
                show_assignee_selection_menu(chat_id, user_state, call)
                return

            if markup:
                bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif data == "calendar_skip_date":
        # Без срока
        from bot.handlers.utils import get_user_state, set_user_state
        chat_id = str(call.message.chat.id)
        user_state = get_user_state(chat_id)

        if user_state:
            if context.startswith("task_editing_"):
                task_id = context.split("_")[2]
                from bot.models import Task
                try:
                    task = Task.objects.get(id=int(task_id))
                    task.due_date = None
                    task.save()
                    text = "✅ Срок задачи снят"
                    from bot.keyboards import get_task_actions_markup
                    markup = get_task_actions_markup(task.id, task.status, task.report_attachments,
                                                   task.creator.telegram_id == chat_id,
                                                   task.assignee.telegram_id == chat_id)
                except Exception as e:
                    logger.error(f"Ошибка при снятии срока задачи: {e}")
                    text = "❌ Ошибка при снятии срока задачи"
                    markup = None
            else:
                user_state['due_date'] = None
                user_state['state'] = 'waiting_assignee_selection'
                set_user_state(chat_id, user_state)

                from bot.handlers.task_creation import show_assignee_selection_menu
                show_assignee_selection_menu(chat_id, user_state, call)
                return

            if markup:
                bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif data == "calendar_back_to_date":
        # Возврат к выбору даты
        text, markup = create_calendar()
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif data == "calendar_cancel":
        # Отмена
        from bot.handlers.utils import clear_user_state
        clear_user_state(str(call.message.chat.id))

        if context.startswith("task_editing_"):
            task_id = context.split("_")[2]
            from bot.keyboards import get_task_actions_markup
            from bot.models import Task
            try:
                task = Task.objects.get(id=int(task_id))
                text = "❌ Изменение срока отменено"
                markup = get_task_actions_markup(task.id, task.status, task.report_attachments,
                                               task.creator.telegram_id == str(call.message.chat.id),
                                               task.assignee.telegram_id == str(call.message.chat.id))
            except:
                text = "❌ Ошибка при отмене"
                markup = None
        else:
            text = "❌ Создание задачи отменено"
            from bot.keyboards import TASK_MANAGEMENT_MARKUP
            markup = TASK_MANAGEMENT_MARKUP

        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif data == "calendar_ignore":
        # Игнорируем нажатие на заголовок или неактивные дни
        pass


def show_calendar(chat_id: str, context: str = "task_creation", message_id: int = None) -> None:
    """
    Показывает календарь пользователю
    """
    text, markup = create_calendar()

    if message_id:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=markup)
    else:
        bot.send_message(chat_id, text, reply_markup=markup)