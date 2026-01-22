from datetime import datetime, timedelta
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from django.utils import timezone
from bot import bot, logger
import calendar as cal


def create_calendar(year: int = None, month: int = None, is_tutorial: bool = False) -> tuple[str, InlineKeyboardMarkup]:
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
                    # Прошедшие дни - не показываем (пустая ячейка)
                    week_buttons.append(InlineKeyboardButton(" ", callback_data="calendar_ignore"))
                else:
                    # Сегодня и будущие дни - активные
                    week_buttons.append(InlineKeyboardButton(str(day), callback_data=f"calendar_date_{year}_{month}_{day}"))

        markup.row(*week_buttons)

    # Кнопки управления
    controls = [InlineKeyboardButton("Без срока", callback_data="calendar_skip_date")]
    if not is_tutorial:
        controls.append(InlineKeyboardButton("⬅️ Отмена", callback_data="calendar_cancel"))
    markup.row(*controls)

    text = "📅 Выберите дату выполнения задачи:"

    return text, markup


def create_time_selector(selected_date: datetime = None) -> tuple[str, InlineKeyboardMarkup]:
    """
    Создает селектор времени
    Если selected_date - сегодняшняя дата, то не показываем прошедшее время
    """
    markup = InlineKeyboardMarkup()
    now = timezone.now()

    # Предустановленные времена
    all_times = [
        ("00:00", "0_00", 0), ("08:00", "8_00", 8), ("12:00", "12_00", 12),
        ("17:00", "17_00", 17), ("21:00", "21_00", 21)
    ]

    # Фильтруем времена, если выбрана сегодняшняя дата
    times = []
    is_today = selected_date and selected_date.date() == now.date()
    
    for time_text, time_data, hour in all_times:
        if is_today:
            # Если сегодня, показываем только будущее время
            if hour > now.hour or (hour == now.hour and now.minute < 59):
                times.append((time_text, time_data))
        else:
            # Если не сегодня, показываем все времена
            times.append((time_text, time_data))

    # Добавляем все доступные кнопки в один ряд
    if times:
        row = []
        for time_text, time_data in times:
            row.append(InlineKeyboardButton(time_text, callback_data=f"calendar_time_{time_data}"))
        markup.row(*row)

    # Дополнительные опции
    markup.row(
        InlineKeyboardButton("Без времени", callback_data="calendar_no_time"),
        InlineKeyboardButton("⬅️ Назад", callback_data="calendar_back_to_date")
    )

    text = "⏰ Выберите время выполнения задачи:"

    return text, markup


def process_calendar_callback(call) -> None:
    """
    Обрабатывает callback'и календаря
    """
    from bot.handlers.utils import get_user_state
    chat_id = str(call.message.chat.id)
    user_state = get_user_state(chat_id)
    context = user_state.get('calendar_context', 'task_creation')
    data = call.data
    logger.info(f"Обработка callback календаря: {data}, context: {context}")

    if data.startswith("calendar_prev_"):
        # Предыдущий месяц
        parts = data.split("_")
        if len(parts) != 4:
            logger.error(f"Неверный формат callback_data для prev: {data}")
            return

        _, _, year, month = parts
        try:
            year, month = int(year), int(month)
            text, markup = create_calendar(year, month)
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
        except ValueError:
            logger.error(f"Неверные числовые значения в prev: {data}")
            return

    elif data.startswith("calendar_next_"):
        # Следующий месяц
        parts = data.split("_")
        if len(parts) != 4:
            logger.error(f"Неверный формат callback_data для next: {data}")
            return

        _, _, year, month = parts
        try:
            year, month = int(year), int(month)
            text, markup = create_calendar(year, month)
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
        except ValueError:
            logger.error(f"Неверные числовые значения в next: {data}")
            return

    elif data.startswith("calendar_date_"):
        # Выбрана дата, показываем время
        parts = data.split("_")
        if len(parts) != 5:
            logger.error(f"Неверный формат callback_data для даты: {data}")
            return

        _, _, year, month, day = parts
        try:
            year, month, day = int(year), int(month), int(day)
        except ValueError:
            logger.error(f"Неверные числовые значения в дате: {data}")
            return

        # Сохраняем выбранную дату в состоянии пользователя
        from bot.handlers.utils import get_user_state, set_user_state
        chat_id = str(call.message.chat.id)
        user_state = get_user_state(chat_id)

        # Проверяем, не является ли выбранная дата прошедшей
        selected_date = datetime(year, month, day)
        selected_date = selected_date.replace(tzinfo=timezone.get_current_timezone())
        now = timezone.now()
        today = now.date()

        if selected_date.date() < today:
            bot.answer_callback_query(call.id, "❌ Нельзя выбрать прошедшую дату", show_alert=True)
            return

        if user_state:
            user_state['selected_date'] = f"{year}-{month:02d}-{day:02d}"
            set_user_state(chat_id, user_state)

        text, markup = create_time_selector(selected_date)
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif data.startswith("calendar_past_date_"):
        # Нажата прошедшая дата - показываем уведомление
        parts = data.split("_")
        if len(parts) == 5:
            _, _, year, month, day = parts
            try:
                year, month, day = int(year), int(month), int(day)
                date_str = f"{day:02d}.{month:02d}.{year}"
                bot.answer_callback_query(call.id, f"❌ Дата {date_str} уже прошла", show_alert=True)
            except ValueError:
                bot.answer_callback_query(call.id, "❌ Прошедшая дата", show_alert=True)
        else:
            bot.answer_callback_query(call.id, "❌ Прошедшая дата", show_alert=True)

    elif data.startswith("calendar_time_"):
        # Выбрано время, сохраняем полную дату и время
        parts = data.split("_")
        if len(parts) != 4:
            logger.error(f"Неверный формат callback_data для времени: {data}")
            return

        _, _, hour, minute = parts
        try:
            hour, minute = int(hour), int(minute)
        except ValueError:
            logger.error(f"Неверные числовые значения во времени: {data}")
            return

        from bot.handlers.utils import get_user_state, set_user_state
        chat_id = str(call.message.chat.id)
        user_state = get_user_state(chat_id)

        if user_state and 'selected_date' in user_state:
            date_str = user_state['selected_date']
            datetime_str = f"{date_str} {hour:02d}:{minute:02d}"
            due_date = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M')
            due_date = due_date.replace(tzinfo=timezone.get_current_timezone())

            # Проверяем, не прошло ли выбранное время
            now = timezone.now()
            if due_date <= now:
                bot.answer_callback_query(call.id, "❌ Нельзя выбрать прошедшее время", show_alert=True)
                return

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
                user_state['due_date'] = due_date.isoformat()  # Сохраняем как строку ISO
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

            # Проверяем, не прошла ли выбранная дата
            now = timezone.now()
            if due_date.date() < now.date():
                bot.answer_callback_query(call.id, "❌ Нельзя выбрать прошедшую дату", show_alert=True)
                return

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
                user_state['due_date'] = due_date.isoformat()  # Сохраняем как строку ISO
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
        # Просто ничего не делаем - кнопка неактивна
        pass

    else:
        # Неизвестный callback - игнорируем
        logger.warning(f"Неизвестный callback календаря: {data}")
        pass


def show_calendar(chat_id: str, context: str = "task_creation", message_id: int = None) -> None:
    """
    Показывает календарь пользователю
    """
    from bot.handlers.utils import get_user_state, set_user_state
    user_state = get_user_state(chat_id)
    user_state['calendar_context'] = context
    set_user_state(chat_id, user_state)
    
    is_tutorial = user_state and user_state.get('is_tutorial')
    text, markup = create_calendar(is_tutorial=is_tutorial)
    
    if is_tutorial:
        text = "📅 **ШАГ 5: СРОК ВЫПОЛНЕНИЯ**\n\nТы можешь указать дату и время, до которых задачу нужно выполнить. Это удобно для планирования.\n\n" + text
        text += "\n\n_Выбери дату на календаре или нажми 'Пропустить срок'._"
        markup.add(InlineKeyboardButton("Пропустить срок", callback_data="skip_due_date"))

    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode='Markdown')
        except Exception:
            bot.send_message(chat_id, text, reply_markup=markup, parse_mode='Markdown')
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode='Markdown')