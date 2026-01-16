from datetime import datetime, timedelta
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from django.utils import timezone
from bot import bot, logger
import calendar as cal


def create_calendar(year: int = None, month: int = None) -> tuple[str, InlineKeyboardMarkup]:
    """
    Создает календарь для выбора даты
    """
    now = timezone.now()
    if year is None:
        year = now.year
    if month is None:
        month = now.month

    markup = InlineKeyboardMarkup()

    # Заголовок с месяцем и годом
    month_names = [
        "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
        "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
    ]

    # Кнопки навигации
    nav_buttons = []
    if month > 1:
        nav_buttons.append(InlineKeyboardButton("◀️", callback_data=f"calendar_prev_{year}_{month}"))
    else:
        nav_buttons.append(InlineKeyboardButton("◀️", callback_data=f"calendar_prev_{year-1}_{12}"))

    nav_buttons.append(InlineKeyboardButton(f"{month_names[month-1]} {year}", callback_data="calendar_ignore"))

    if month < 12:
        nav_buttons.append(InlineKeyboardButton("▶️", callback_data=f"calendar_next_{year}_{month}"))
    else:
        nav_buttons.append(InlineKeyboardButton("▶️", callback_data=f"calendar_next_{year+1}_{1}"))

    markup.row(*nav_buttons)

    # Дни недели
    week_days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    markup.row(*[InlineKeyboardButton(day, callback_data="calendar_ignore") for day in week_days])

    # Получаем календарь для месяца
    month_calendar = cal.monthcalendar(year, month)

    # Создаем кнопки для дней
    for week in month_calendar:
        week_buttons = []
        for day in week:
            if day == 0:
                # Пустая ячейка
                week_buttons.append(InlineKeyboardButton(" ", callback_data="calendar_ignore"))
            else:
                current_date = datetime(year, month, day).date()
                today = now.date()

                if current_date < today:
                    # Прошедшие дни - неактивные
                    week_buttons.append(InlineKeyboardButton(str(day), callback_data="calendar_ignore"))
                else:
                    # Будущие дни - активные
                    week_buttons.append(InlineKeyboardButton(str(day), callback_data=f"calendar_date_{year}_{month}_{day}"))

        markup.row(*week_buttons)

    # Кнопки управления
    markup.row(
        InlineKeyboardButton("Без срока", callback_data="calendar_skip_date"),
        InlineKeyboardButton("⬅️ Отмена", callback_data="calendar_cancel")
    )

    text = "📅 Выберите дату выполнения задачи:"

    return text, markup


def create_time_selector(selected_date: str = None) -> tuple[str, InlineKeyboardMarkup]:
    """
    Создает селектор времени
    """
    markup = InlineKeyboardMarkup()

    # Предустановленные времена
    times = [
        ("09:00", "09:00"), ("10:00", "10:00"), ("11:00", "11:00"),
        ("12:00", "12:00"), ("13:00", "13:00"), ("14:00", "14:00"),
        ("15:00", "15:00"), ("16:00", "16:00"), ("17:00", "17:00"),
        ("18:00", "18:00"), ("19:00", "19:00"), ("20:00", "20:00")
    ]

    # Добавляем ряды по 4 кнопки
    for i in range(0, len(times), 4):
        row = []
        for time_text, time_value in times[i:i+4]:
            callback_data = f"calendar_time_{selected_date}_{time_value}" if selected_date else f"calendar_time_{time_value}"
            row.append(InlineKeyboardButton(time_text, callback_data=callback_data))
        markup.row(*row)

    # Дополнительные опции
    markup.row(
        InlineKeyboardButton("Без времени", callback_data=f"calendar_no_time_{selected_date}" if selected_date else "calendar_no_time"),
        InlineKeyboardButton("⬅️ Назад", callback_data="calendar_back_to_date")
    )

    date_text = f" ({selected_date})" if selected_date else ""
    text = f"⏰ Выберите время выполнения задачи{date_text}:"

    return text, markup


def process_calendar_callback(call) -> None:
    """
    Обрабатывает callback'и календаря
    Контекст извлекается из callback_data
    """
    data = call.data

    # Извлекаем контекст из конца callback_data
    parts = data.split("_")
    context_found = False
    context = "task_creation"
    data_without_context = data

    # Ищем контекст в конце (task_creation или task_editing_{id})
    if len(parts) >= 2:
        # Проверяем на task_creation
        if "_".join(parts[-2:]) == "task_creation":
            context = "task_creation"
            data_without_context = "_".join(parts[:-2])
            context_found = True
        # Проверяем на task_editing_{id}
        elif len(parts) >= 3 and "_".join(parts[-3:-1]) == "task_editing":
            context = f"task_editing_{parts[-1]}"
            data_without_context = "_".join(parts[:-3])
            context_found = True

    if not context_found:
        # Если контекст не найден, используем по умолчанию
        context = "task_creation"
        data_without_context = data

    try:
        if data_without_context.startswith("calendar_prev"):
            # Предыдущий месяц
            _, year, month = data_without_context.split("_", 2)
            year, month = int(year), int(month)
            text, markup = create_calendar_with_context(year, month, context)
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

        elif data_without_context.startswith("calendar_next"):
            # Следующий месяц
            _, year, month = data_without_context.split("_", 2)
            year, month = int(year), int(month)
            text, markup = create_calendar_with_context(year, month, context)
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

        elif data_without_context.startswith("calendar_date"):
            # Выбрана дата, показываем время
            _, year, month, day = data_without_context.split("_", 3)
            year, month, day = int(year), int(month), int(day)
            date_str = f"{year:04d}-{month:02d}-{day:02d}"

            text, markup = create_time_selector(date_str)
            # Добавляем контекст к callback_data времени
            if markup.keyboard:
                for row in markup.keyboard:
                    for button in row:
                        if hasattr(button, 'callback_data') and button.callback_data and not button.callback_data.endswith("_date"):
                            button.callback_data = f"{button.callback_data}_{context}"

            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

        elif data_without_context.startswith("calendar_time"):
            # Выбрано время, сохраняем полную дату и время
            parts = data_without_context.split("_", 2)
            if len(parts) >= 3:  # calendar_time_date_time
                _, date_str, time_str = parts
            else:  # calendar_time_time (старый формат)
                _, time_str = parts
                date_str = None

            if not date_str:
                # Если дата не указана в callback, пробуем получить из состояния
                from bot.handlers.utils import get_user_state
                chat_id = str(call.message.chat.id)
                user_state = get_user_state(chat_id)
                date_str = user_state.get('selected_date') if user_state else None

            if date_str and time_str:
                datetime_str = f"{date_str} {time_str}"
                due_date = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M')
                due_date = due_date.replace(tzinfo=timezone.get_current_timezone())

                _save_due_date(call, due_date, context)

        elif data_without_context.startswith("calendar_no_time"):
            # Без времени - сохраняем только дату
            parts = data_without_context.split("_", 2)
            if len(parts) >= 2:
                date_str = parts[1]
            else:
                # Старый формат без даты
                from bot.handlers.utils import get_user_state
                chat_id = str(call.message.chat.id)
                user_state = get_user_state(chat_id)
                date_str = user_state.get('selected_date') if user_state else None

            if date_str:
                due_date = datetime.strptime(date_str, '%Y-%m-%d')
                due_date = due_date.replace(tzinfo=timezone.get_current_timezone())
                _save_due_date(call, due_date, context)

        elif data_without_context == "calendar_skip_date":
            # Без срока
            _save_due_date(call, None, context)

        elif data_without_context == "calendar_back_to_date":
            # Возврат к выбору даты
            text, markup = create_calendar_with_context(context=context)
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

        elif data_without_context == "calendar_cancel":
            # Отмена
            _handle_calendar_cancel(call, context)

        elif data == "calendar_ignore":
            # Игнорируем нажатие на заголовок или неактивные дни
            pass

    except Exception as e:
        logger.error(f"Ошибка в process_calendar_callback: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка", show_alert=True)


def _save_due_date(call, due_date, context: str) -> None:
    """Сохраняет дату выполнения задачи"""
    chat_id = str(call.message.chat.id)

    try:
        if context.startswith("task_editing_"):
            task_id = context.split("_")[2]
            from bot.models import Task
            task = Task.objects.get(id=int(task_id))
            task.due_date = due_date
            task.save()

            if due_date:
                text = f"✅ Срок задачи обновлен: {due_date.strftime('%d.%m.%Y %H:%M') if due_date.hour else due_date.strftime('%d.%m.%Y')}"
            else:
                text = "✅ Срок задачи снят"

            from bot.keyboards import get_task_actions_markup
            markup = get_task_actions_markup(task.id, task.status, task.report_attachments,
                                           task.creator.telegram_id == chat_id,
                                           task.assignee.telegram_id == chat_id)

        else:
            # Контекст создания задачи
            from bot.handlers.utils import get_user_state, set_user_state
            user_state = get_user_state(chat_id)

            if user_state:
                user_state['due_date'] = due_date
                user_state['state'] = 'waiting_assignee_selection'
                set_user_state(chat_id, user_state)

                from bot.handlers.task_creation import show_assignee_selection_menu
                show_assignee_selection_menu(chat_id, user_state, call)
                return

            text = "❌ Ошибка: состояние пользователя не найдено"
            markup = None

        if markup:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

    except Exception as e:
        logger.error(f"Ошибка при сохранении даты: {e}")
        bot.edit_message_text("❌ Ошибка при сохранении даты", call.message.chat.id, call.message.message_id)


def _handle_calendar_cancel(call, context: str) -> None:
    """Обрабатывает отмену календаря"""
    from bot.handlers.utils import clear_user_state

    try:
        clear_user_state(str(call.message.chat.id))

        if context.startswith("task_editing_"):
            task_id = context.split("_")[2]
            from bot.keyboards import get_task_actions_markup
            from bot.models import Task
            task = Task.objects.get(id=int(task_id))
            text = "❌ Изменение срока отменено"
            markup = get_task_actions_markup(task.id, task.status, task.report_attachments,
                                           task.creator.telegram_id == str(call.message.chat.id),
                                           task.assignee.telegram_id == str(call.message.chat.id))
        else:
            text = "❌ Создание задачи отменено"
            from bot.keyboards import TASK_MANAGEMENT_MARKUP
            markup = TASK_MANAGEMENT_MARKUP

        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

    except Exception as e:
        logger.error(f"Ошибка при отмене календаря: {e}")
        bot.edit_message_text("❌ Ошибка при отмене", call.message.chat.id, call.message.message_id)


def show_calendar(chat_id: str, context: str = "task_creation", message_id: int = None) -> None:
    """
    Показывает календарь пользователю
    """
    text, markup = create_calendar_with_context(context=context)

    if message_id:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=markup)
    else:
        bot.send_message(chat_id, text, reply_markup=markup)


def create_calendar_with_context(year: int = None, month: int = None, context: str = "task_creation") -> tuple[str, InlineKeyboardMarkup]:
    """
    Создает календарь с учетом контекста (для callback_data)
    """
    text, markup = create_calendar(year, month)

    # Обновляем все callback_data, добавляя контекст
    if markup.keyboard:
        for row in markup.keyboard:
            for button in row:
                if hasattr(button, 'callback_data') and button.callback_data:
                    if not button.callback_data.startswith("calendar_ignore"):
                        button.callback_data = f"{button.callback_data}_{context}"

    return text, markup