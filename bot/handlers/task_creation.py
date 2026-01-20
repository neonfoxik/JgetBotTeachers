from bot.handlers.utils import (
    get_or_create_user, get_chat_id_from_update, safe_edit_or_send_message, get_user_state,
    set_user_state, clear_user_state, check_permissions, format_task_info, parse_datetime_from_state
)
from bot import bot, logger
from bot.models import User, Task, Subtask
from bot.keyboards import (
    get_user_selection_markup, TASK_MANAGEMENT_MARKUP
)
from telebot.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import transaction
from datetime import datetime
from django.utils import timezone


def show_assignee_selection_menu(chat_id: str, user_state: dict, call: CallbackQuery = None) -> None:
    """Показывает меню выбора исполнителя с тремя кнопками: Я сам, Выбрать пользователя, Отмена"""
    text = "👤 **ШАГ 6: ИСПОЛНИТЕЛЬ**\n\n"
    if user_state.get('is_tutorial'):
        text += "Теперь нужно выбрать, КТО будет выполнять задачу. Ты можешь назначить её **себе** или любому другому пользователю бота.\n\n_Нажми 'Я сам', чтобы продолжить обучение._"
    else:
        text += f"Выберите исполнителя для задачи '{user_state.get('title', '')}':"

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("👤 Я сам", callback_data="assign_to_me"))
    markup.add(InlineKeyboardButton("👥 Выбрать пользователя", callback_data="choose_user_from_list"))
    if not user_state.get('is_tutorial'):
        markup.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel_task_creation"))

    if call:
        safe_edit_or_send_message(chat_id, text, reply_markup=markup, message_id=call.message.message_id, parse_mode='Markdown')
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode='Markdown')


def show_subtasks_menu(chat_id: str, user_state: dict, call: CallbackQuery = None) -> None:
    """Показывает меню управления подзадачами"""
    subtasks = user_state.get('subtasks', [])
    
    text = "📋 **ШАГ 3: ПОДЗАДАЧИ**\n\n"
    if user_state.get('is_tutorial'):
        text += "Большие задачи лучше делить на части. Ты можешь добавить несколько пунктов, которые нужно выполнить.\n\n"
    else:
        text += f"Подзадачи для '{user_state.get('title', '')}':\n\n"

    if subtasks:
        text += "**Текущие подзадачи:**\n"
        for i, subtask in enumerate(subtasks, 1):
            text += f"{i}. {subtask}\n"
        text += "\n"
    else:
        if user_state.get('is_tutorial'):
            text += "_Подзадачи пока не добавлены. Попробуй добавить одну или нажми 'Готово'._\n\n"
        else:
            text += "Подзадачи пока не добавлены.\n\n"

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("➕ Добавить подзадачу", callback_data="add_subtask"))
    if subtasks:
        markup.add(InlineKeyboardButton("🗑️ Очистить все подзадачи", callback_data="clear_subtasks"))
    markup.add(InlineKeyboardButton("✅ Готово", callback_data="finish_subtasks"))

    if not user_state.get('is_tutorial'):
        markup.add(InlineKeyboardButton("⬅️ Отмена", callback_data="cancel_task_creation"))

    if call:
        safe_edit_or_send_message(chat_id, text, reply_markup=markup, message_id=call.message.message_id, parse_mode='Markdown')
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode='Markdown')


def show_user_selection_list(chat_id: str, user_state: dict, call: CallbackQuery = None) -> None:
    """Показывает список всех пользователей с пагинацией"""
    text = f"👤 Выберите исполнителя для задачи '{user_state.get('title', '')}'\n\n"
    text += "Выберите пользователя из списка:"

    users = list(User.objects.all())
    markup = get_user_selection_markup(users)

    if call:
        safe_edit_or_send_message(chat_id, text, reply_markup=markup, message_id=call.message.message_id, parse_mode='Markdown')
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
            due_date_parsed = parse_datetime_from_state(user_state.get('due_date'))
            task = Task.objects.create(
                title=user_state['title'],
                description=user_state['description'],
                creator=creator,
                assignee=assignee,
                due_date=due_date_parsed,
                attachments=user_state.get('attachments', [])
            )

            # Создаем подзадачи, если они были добавлены
            subtasks = user_state.get('subtasks', [])
            for subtask_title in subtasks:
                Subtask.objects.create(
                    task=task,
                    title=subtask_title
                )
            # Логируем создание в историю
            from bot.handlers.utils import log_task_history
            log_task_history(task, creator, "Задача создана")
            logger.info(f"Задача {task.id} успешно создана и история записана.")

            success_msg = f"✅ Задача '{task.title}' успешно создана!\n\n"
            success_msg += f"🆔 ID в базе: {task.id}\n"
            # Удаляем Markdown форматирование для имени, так как оно может содержать '_'
            success_msg += f"👤 Исполнитель: {assignee.user_name} (ID: {assignee.telegram_id})\n"
            if task.due_date:
                success_msg += f"⏰ Срок: {task.due_date.strftime('%d.%m.%Y %H:%M')}"
            if subtasks:
                success_msg += f"📋 Подзадач: {len(subtasks)}"
            
            # Временно добавим отладочную инфо о БД (без Markdown)
            from django.conf import settings
            db_name = settings.DATABASES['default']['NAME']
            success_msg += f"\n\n⚙️ Debug: DB={db_name}"

            if user_state.get('is_tutorial') or user_state.get('state') == 'tutorial_waiting_for_creation':
                from bot.handlers.tutorial import tutorial_task_created
                tutorial_task_created(chat_id, task.id)
                return True, success_msg, None # Tutorial handles its own message

            return True, success_msg, TASK_MANAGEMENT_MARKUP

    except Exception as e:
        logger.error(f"Ошибка при создании задачи для {chat_id}: {e}", exc_info=True)
        return False, f"❌ Ошибка при создании задачи: {str(e)}", TASK_MANAGEMENT_MARKUP


def handle_task_creation_messages(message: Message) -> None:
    chat_id = str(message.chat.id)
    logger.info(f"Получено сообщение от {chat_id}: '{message.text}'")
    
    try:
        user_state = get_user_state(chat_id)
        logger.info(f"Состояние пользователя {chat_id}: {user_state}")
        
        # Проверяем, есть ли состояние и оно связано с созданием задачи или добавлением подзадач
        if not user_state:
            logger.info(f"Нет состояния для пользователя {chat_id}")
            return

        # Проверяем на добавление подзадач к существующей задаче
        if 'adding_subtasks_task_id' in user_state:
            logger.info(f"Обработка добавления подзадач для пользователя {chat_id}")
            # Обработка добавления подзадач к существующей задаче
            task_id = user_state['adding_subtasks_task_id']
            try:
                task = Task.objects.get(id=task_id)
                chat_id = str(message.chat.id)
                allowed, error_msg = check_permissions(chat_id, task, require_creator=True)
                if not allowed:
                    bot.send_message(message.chat.id, error_msg)
                    clear_user_state(chat_id)
                    return

                if task.status == 'completed':
                    bot.send_message(message.chat.id, "❌ Нельзя добавлять подзадачи к завершенной задаче")
                    clear_user_state(chat_id)
                    return

                # Разбираем подзадачи по строкам
                subtasks_text = message.text.strip()
                if not subtasks_text:
                    bot.send_message(message.chat.id, "❌ Список подзадач не может быть пустым")
                    return

                subtasks = [line.strip() for line in subtasks_text.split('\n') if line.strip()]

                if not subtasks:
                    bot.send_message(message.chat.id, "❌ Не найдено ни одной подзадачи")
                    return

                # Создаем подзадачи
                from bot.models import Subtask
                created_count = 0
                for subtask_title in subtasks:
                    if len(subtask_title) > 3:  # Минимум 3 символа для названия
                        Subtask.objects.create(
                            task=task,
                            title=subtask_title
                        )
                        created_count += 1

                # Очищаем состояние
                clear_user_state(chat_id)

                # Обновляем прогресс задачи
                task.update_progress()

                text = f"✅ Добавлено {created_count} подзадач к задаче '{task.title}'"
                bot.send_message(message.chat.id, text, reply_markup=TASK_MANAGEMENT_MARKUP)

            except Task.DoesNotExist:
                bot.send_message(message.chat.id, "❌ Задача не найдена")
                clear_user_state(chat_id)
            except Exception as e:
                logger.error(f"Ошибка при добавлении подзадач: {e}")
                bot.send_message(message.chat.id, "❌ Произошла ошибка при добавлении подзадач")
                clear_user_state(chat_id)
            return

        # Проверяем на редактирование задачи
        if 'editing_task_id' in user_state:
            task_id = user_state['editing_task_id']
            field = user_state.get('editing_field')
            try:
                task = Task.objects.get(id=task_id)
                if field == 'title':
                    if len(message.text.strip()) < 3:
                        bot.send_message(message.chat.id, "❌ Название задачи должно содержать минимум 3 символа")
                        return
                    task.title = message.text.strip()
                    task.save()
                    bot.send_message(message.chat.id, f"✅ Название задачи #{task_id} изменено")
                elif field == 'description':
                    task.description = message.text.strip()
                    task.save()
                    bot.send_message(message.chat.id, f"✅ Описание задачи #{task_id} изменено")
                
                # Очищаем состояние
                clear_user_state(chat_id)
                
                # Показываем обновленную информацию о задаче
                from bot.handlers.utils import show_task_progress
                is_creator = str(task.creator.telegram_id) == str(chat_id)
                is_assignee = str(task.assignee.telegram_id) == str(chat_id)
                show_task_progress(chat_id, task, is_creator, is_assignee)
                return
            except Task.DoesNotExist:
                bot.send_message(message.chat.id, "❌ Задача не найдена")
                clear_user_state(chat_id)
                return
            except Exception as e:
                logger.error(f"Ошибка при редактировании задачи: {e}")
                bot.send_message(message.chat.id, "❌ Произошла ошибка при сохранении изменений")
                clear_user_state(chat_id)
                return

        # Проверяем на создание задачи
        state = user_state.get('state')
        if not state:
            logger.info(f"Нет активного состояния создания задачи для пользователя {chat_id}")
            return

        logger.info(f"Текущее состояние: {state}")

        # Проверяем, что состояние относится к созданию задачи
        if state not in ['waiting_task_title', 'waiting_task_description', 'waiting_subtasks', 'waiting_subtask_input', 'waiting_due_date', 'waiting_attachments']:
            logger.info(f"Состояние {state} не относится к созданию задачи, пропускаем")
            return

        if state == 'waiting_task_title':
            if len(message.text.strip()) < 3:
                bot.send_message(message.chat.id, "❌ Название задачи должно содержать минимум 3 символа")
                return
            user_state['title'] = message.text.strip()
            user_state['state'] = 'waiting_task_description'
            set_user_state(str(message.chat.id), user_state)
            
            text = "📝 **ШАГ 2: ОПИСАНИЕ**\n\nТеперь введи подробности задачи или нажми 'Пропустить'.\n\n"
            if user_state.get('is_tutorial'):
                text += "_Здесь можно написать детали: что именно нужно сделать, какие-то ссылки или важные заметки._"
            else:
                text += "Введите описание задачи:"
                
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("Пропустить описание", callback_data="skip_description"))
            if not user_state.get('is_tutorial'):
                markup.add(InlineKeyboardButton("⬅️ Отмена", callback_data="cancel_task_creation"))
            bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode='Markdown')

        elif state == 'waiting_task_description':
            user_state['description'] = None if message.text.lower() in ['пусто', 'skip', 'пропустить'] else message.text.strip()
            user_state['subtasks'] = []  # Инициализируем список подзадач
            user_state['state'] = 'waiting_subtasks'
            set_user_state(str(message.chat.id), user_state)
            show_subtasks_menu(str(message.chat.id), user_state)

        elif state == 'waiting_subtask_input':
            # Добавляем введенную подзадачу к списку
            if message.text.strip():
                user_state['subtasks'].append(message.text.strip())
                set_user_state(str(message.chat.id), user_state)
                show_subtasks_menu(str(message.chat.id), user_state)
            else:
                bot.send_message(message.chat.id, "❌ Название подзадачи не может быть пустым. Попробуйте еще раз:")

        elif state == 'waiting_due_date':
            # Показываем календарь вместо текстового ввода
            from bot.handlers.calendar import show_calendar
            show_calendar(str(message.chat.id), "task_creation")

        elif state == 'waiting_attachments':
            # Обрабатываем вложения
            attachments = user_state.get('attachments', [])
            
            if message.photo:
                # Получаем самое большое фото
                photo = message.photo[-1]
                attachments.append({
                    'type': 'photo',
                    'file_id': photo.file_id
                })
                bot.send_message(message.chat.id, "✅ Фото добавлено. Вы можете прикрепить еще или нажать 'Готово'.")
            elif message.document:
                attachments.append({
                    'type': 'document',
                    'file_id': message.document.file_id,
                    'file_name': message.document.file_name
                })
                bot.send_message(message.chat.id, "✅ Файл добавлен. Вы можете прикрепить еще или нажать 'Готово'.")
            else:
                bot.send_message(message.chat.id, "❌ Пожалуйста, отправьте фото или файл, либо нажмите 'Готово'.")
                return

            user_state['attachments'] = attachments
            set_user_state(chat_id, user_state)
            show_attachments_menu(chat_id, user_state)

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
        user_state['subtasks'] = []  # Инициализируем список подзадач
        user_state['state'] = 'waiting_subtasks'
        set_user_state(chat_id, user_state)
        show_subtasks_menu(chat_id, user_state, call)


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
        
        # Очищаем состояние только при успехе и если это не туториал
        if success:
            if user_state.get('state') != 'tutorial_waiting_for_creation' and not user_state.get('is_tutorial'):
                clear_user_state(chat_id)
            
        safe_edit_or_send_message(call.message.chat.id, msg, reply_markup=markup, message_id=call.message.message_id, parse_mode='Markdown')




def assign_to_me_callback(call: CallbackQuery) -> None:
    """Обработчик для кнопки 'Я сам' - назначает задачу себе"""
    assign_to_creator_callback(call)


def choose_user_from_list_callback(call: CallbackQuery) -> None:
    """Обработчик для кнопки 'Выбрать пользователя' - показывает список всех пользователей"""
    chat_id = get_chat_id_from_update(call)
    user_state = get_user_state(chat_id)
    if user_state:
        show_user_selection_list(chat_id, user_state, call)


def add_subtask_callback(call: CallbackQuery) -> None:
    """Обработчик для кнопки 'Добавить подзадачу'"""
    chat_id = get_chat_id_from_update(call)
    user_state = get_user_state(chat_id)
    if user_state:
        user_state['state'] = 'waiting_subtask_input'
        set_user_state(chat_id, user_state)
        text = "📝 Введите название подзадачи:"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("⬅️ Отмена", callback_data="cancel_subtask_input"))
        safe_edit_or_send_message(chat_id, text, reply_markup=markup, message_id=call.message.message_id, parse_mode='Markdown')


def cancel_subtask_input_callback(call: CallbackQuery) -> None:
    """Обработчик для отмены ввода подзадачи"""
    chat_id = get_chat_id_from_update(call)
    user_state = get_user_state(chat_id)
    if user_state:
        user_state['state'] = 'waiting_subtasks'
        set_user_state(chat_id, user_state)
        show_subtasks_menu(chat_id, user_state, call)


def clear_subtasks_callback(call: CallbackQuery) -> None:
    """Обработчик для очистки всех подзадач"""
    chat_id = get_chat_id_from_update(call)
    user_state = get_user_state(chat_id)
    if user_state:
        user_state['subtasks'] = []
        set_user_state(chat_id, user_state)
        show_subtasks_menu(chat_id, user_state, call)


def finish_subtasks_callback(call: CallbackQuery) -> None:
    """Переход от подзадач к вложениям"""
    chat_id = get_chat_id_from_update(call)
    user_state = get_user_state(chat_id)
    if user_state:
        show_attachments_menu(chat_id, user_state, call)

def show_attachments_menu(chat_id: str, user_state: dict, call: CallbackQuery = None) -> None:
    """Меню загрузки вложений (фото, файлы)"""
    user_state['state'] = 'waiting_attachments'
    set_user_state(chat_id, user_state)
    
    attachments = user_state.get('attachments', [])
    text = "📎 **ШАГ 4: ВЛОЖЕНИЯ (ОПЦИОНАЛЬНО)**\n\n"
    if user_state.get('is_tutorial'):
        text += "Ты можешь прикрепить к задаче фото или документы. Просто отправь их боту в этом чате.\n\n"
    else:
        text += "Отправьте боту фото или файлы, чтобы прикрепить их к задаче.\n\n"
        
    if attachments:
        text += f"✅ **Уже добавлено: {len(attachments)}**\n\n"
    
    text += "_Нажми 'Готово', когда закончишь, или если вложения не нужны._"
    
    markup = InlineKeyboardMarkup()
    if attachments:
        markup.add(InlineKeyboardButton("🗑️ Очистить список", callback_data="clear_attachments"))
    markup.add(InlineKeyboardButton("✅ Готово", callback_data="finish_attachments"))
    if not user_state.get('is_tutorial'):
        markup.add(InlineKeyboardButton("⬅️ Назад", callback_data="cancel_task_creation"))
    
    if call:
        safe_edit_or_send_message(chat_id, text, reply_markup=markup, message_id=call.message.message_id, parse_mode='Markdown')
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode='Markdown')

def clear_attachments_callback(call: CallbackQuery) -> None:
    chat_id = get_chat_id_from_update(call)
    user_state = get_user_state(chat_id)
    if user_state:
        user_state['attachments'] = []
        show_attachments_menu(chat_id, user_state, call)

def finish_attachments_callback(call: CallbackQuery) -> None:
    """Переход от вложений к сроку выполнения"""
    chat_id = get_chat_id_from_update(call)
    user_state = get_user_state(chat_id)
    if user_state:
        user_state['state'] = 'waiting_due_date'
        set_user_state(chat_id, user_state)
        from bot.handlers.calendar import show_calendar
        show_calendar(chat_id, "task_creation", call.message.message_id)


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
    # Проверяем тип users - если это QuerySet, используем count(), иначе len()
    if hasattr(users, 'count') and not isinstance(users, list):
        try:
            total_users = users.count()
        except (TypeError, AttributeError):
            total_users = len(users)
    else:
        total_users = len(users)
    total_pages = (total_users + users_per_page - 1) // users_per_page if total_users > 0 else 1
    text = f"👤 Выберите исполнителя (страница {page + 1} из {total_pages}):"
    safe_edit_or_send_message(call.message.chat.id, text, reply_markup=markup, message_id=call.message.message_id, parse_mode='Markdown')


def select_user_callback(call: CallbackQuery) -> None:
    try:
        assignee_telegram_id = call.data.split('_')[2]
        chat_id = get_chat_id_from_update(call)
        user_state = get_user_state(chat_id)

        if user_state:
            if user_state.get('editing_field') == 'assignee' and 'editing_task_id' in user_state:
                task_id = user_state['editing_task_id']
                task = Task.objects.get(id=task_id)
                new_assignee = User.objects.get(telegram_id=assignee_telegram_id)
                old_assignee = task.assignee
                
                if old_assignee.telegram_id == new_assignee.telegram_id:
                    bot.answer_callback_query(call.id, "⚠️ Этот пользователь уже является исполнителем", show_alert=True)
                    return
                
                task.assignee = new_assignee
                try:
                    task.save()
                except ValidationError as ve:
                    bot.answer_callback_query(call.id, f"❌ Ошибка валидации: {ve.message}", show_alert=True)
                    return
                
                # Уведомляем нового исполнителя
                try:
                    bot.send_message(
                        new_assignee.telegram_id,
                        f"📋 ВАМ НАЗНАЧЕНА ЗАДАЧА\n\n{format_task_info(task)}"
                    )
                except Exception:
                    pass
                
                clear_user_state(chat_id)
                text = f"✅ Исполнитель задачи '{task.title}' изменен с {old_assignee.user_name} на {new_assignee.user_name}"
                bot.send_message(chat_id, text)
                
                # Показываем обновленную информацию о задаче
                from bot.handlers.utils import show_task_progress
                is_creator = str(task.creator.telegram_id) == str(chat_id)
                is_assignee = str(task.assignee.telegram_id) == str(chat_id)
                show_task_progress(chat_id, task, is_creator, is_assignee)
                return

            user_state['assignee_id'] = assignee_telegram_id
            set_user_state(chat_id, user_state)

            success, msg, markup = create_task_from_state(chat_id, user_state)
            
            # Очищаем состояние только при успехе и если это не туториал
            if success:
                if user_state.get('state') != 'tutorial_waiting_for_creation' and not user_state.get('is_tutorial'):
                    clear_user_state(chat_id)
                
            safe_edit_or_send_message(call.message.chat.id, msg, reply_markup=markup, message_id=call.message.message_id, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Ошибка при выборе пользователя: {e}")
        bot.answer_callback_query(call.id, "Ошибка при выборе пользователя", show_alert=True)


def back_to_assignee_selection_callback(call: CallbackQuery) -> None:
    """Возвращает к меню выбора исполнителя с тремя кнопками"""
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
    safe_edit_or_send_message(call.message.chat.id, text, reply_markup=TASK_MANAGEMENT_MARKUP, message_id=call.message.message_id, parse_mode='Markdown')
