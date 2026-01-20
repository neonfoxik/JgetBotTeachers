from traceback import format_exc
from asgiref.sync import sync_to_async
from bot.handlers import (
    start_command, tasks_command, my_created_tasks_command,
    close_task_command, task_progress_command, debug_command,
    tasks_callback, my_created_tasks_callback,
    create_task_command, create_task_callback,
    handle_task_creation_messages, skip_description_callback, skip_due_date_callback,
    assign_to_creator_callback, assign_to_me_callback, choose_user_from_list_callback,
    add_subtask_callback, cancel_subtask_input_callback, clear_subtasks_callback, finish_subtasks_callback,
    clear_attachments_callback, finish_attachments_callback,
    skip_assignee_callback, choose_assignee_callback,
    user_page_callback, select_user_callback, back_to_assignee_selection_callback,
    back_to_assignee_type_callback, cancel_task_creation_callback,
    task_view_callback, task_progress_callback, task_complete_callback,
    task_confirm_callback, task_reject_callback, subtask_toggle_callback,
    task_delete_callback, confirm_delete_callback, task_status_callback,
    task_edit_callback, edit_title_callback, edit_description_callback,
    edit_assignee_callback, edit_due_date_callback, assignee_page_callback,
    change_assignee_callback, task_close_callback,
    handle_task_report, view_report_attachments_callback,
    tasks_back_callback, main_menu_callback, process_calendar_callback,
    add_subtasks_callback, reopen_task_callback,
    start_tutorial_callback
)
from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from telebot.apihelper import ApiTelegramException
from telebot.types import Update
from bot import bot, logger

@require_GET
def set_webhook(request: HttpRequest) -> JsonResponse:
    hook_url = settings.HOOK
    hook_url = hook_url.rstrip('/')
    if not hook_url.startswith(('http://', 'https://')):
        hook_url = f"https://{hook_url}"
    if hook_url.startswith('http://'):
        hook_url = hook_url.replace('http://', 'https://')
    webhook_url = f"{hook_url}/bot/{settings.BOT_TOKEN}"
    print(f"Setting webhook to: {webhook_url}")  
    try:
        bot.set_webhook(url=webhook_url)
        print("Webhook set successfully")
        if hasattr(settings, 'OWNER_ID') and settings.OWNER_ID:
            try:
                bot.send_message(settings.OWNER_ID, f"Webhook set to: {webhook_url}")
            except Exception as e:
                print(f"Warning: Could not send webhook notification: {e}")
        return JsonResponse({"message": "Webhook set successfully", "webhook_url": webhook_url}, status=200)
    except Exception as e:
        error_msg = f"Failed to set webhook: {str(e)}"
        print(error_msg)
        return JsonResponse({"message": error_msg, "webhook_url": webhook_url}, status=500)
@require_GET
def status(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"message": "OK"}, status=200)
@csrf_exempt
@require_POST
def index(request: HttpRequest) -> JsonResponse:
    try:
        # Проверка Content-Type
        content_type = request.META.get("CONTENT_TYPE", "")
        if "application/json" not in content_type:
            return JsonResponse({"message": "Bad Request: Content-Type must be application/json"}, status=400)
        
        # Декодирование тела запроса
        try:
            json_string = request.body.decode("utf-8")
        except UnicodeDecodeError as e:
            logger.error(f"Unicode decode error: {e}")
            return JsonResponse({"message": "Bad Request: Invalid encoding"}, status=400)
        
        # Парсинг обновления
        try:
            update = Update.de_json(json_string)
            if not update:
                logger.warning("Empty update received")
                return JsonResponse({"message": "OK"}, status=200)
        except Exception as e:
            logger.error(f"Error parsing update: {e} {format_exc()}")
            return JsonResponse({"message": "Bad Request: Invalid update format"}, status=400)
        
        # Обработка обновления
        try:
            bot.process_new_updates([update])
        except ApiTelegramException as e:
            logger.error(f"Telegram API exception: {e} {format_exc()}")
            # Не прерываем выполнение, возвращаем OK
        except ConnectionError as e:
            logger.error(f"Connection error: {e} {format_exc()}")
            # Не прерываем выполнение, возвращаем OK
        except Exception as e:
            logger.error(f"Error processing update: {e} {format_exc()}")
            if hasattr(settings, 'OWNER_ID') and settings.OWNER_ID:
                try:
                    bot.send_message(settings.OWNER_ID, f'Error from index: {e}')
                except Exception as msg_e:
                    logger.warning(f"Could not send error notification: {msg_e}")
        
        # Всегда возвращаем успешный ответ
        return JsonResponse({"message": "OK", "status": "processed"}, status=200)
        
    except Exception as e:
        # Критическая ошибка - логируем и возвращаем ошибку
        logger.error(f"Critical error in index view: {e} {format_exc()}")
        return JsonResponse({"message": "Internal Server Error", "error": str(e)}, status=500)

start_handler = bot.message_handler(commands=["start"])(start_command)
tasks_command_handler = bot.message_handler(commands=["tasks"])(tasks_command)
my_created_tasks_command_handler = bot.message_handler(commands=["my_created_tasks"])(my_created_tasks_command)
close_task_command_handler = bot.message_handler(commands=["close_task"])(close_task_command)
task_progress_command_handler = bot.message_handler(commands=["task_progress"])(task_progress_command)
debug_command_handler = bot.message_handler(commands=["debug"])(debug_command)
create_task_command_handler = bot.message_handler(commands=["create_task"])(create_task_command)

# Callback для команд
tasks_callback_handler = bot.callback_query_handler(func=lambda c: c.data == "tasks")(tasks_callback)
my_created_tasks_callback_handler = bot.callback_query_handler(func=lambda c: c.data == "my_created_tasks")(my_created_tasks_callback)
create_task_callback_handler = bot.callback_query_handler(func=lambda c: c.data == "create_task")(create_task_callback)

# Обработка сообщений (текст, фото, файлы)
@bot.message_handler(content_types=['text', 'photo', 'document'])
def master_message_handler(message: Message):
    if message.text and message.text.startswith('/'):
        return # Игнорируем команды, для них есть свои хендлеры
        
    from bot.handlers.utils import get_user_state
    user_state = get_user_state(str(message.chat.id))
    
    # Если пользователь в процессе создания/редактирования - отправляем туда
    if user_state and (user_state.get('state') or 'editing_task_id' in user_state or 'adding_subtasks_task_id' in user_state):
        handle_task_creation_messages(message)
    else:
        # Иначе пробуем обработать как отчет по задаче
        handle_task_report(message)

# Callback для создания задач
skip_description_handler = bot.callback_query_handler(func=lambda c: c.data == "skip_description")(skip_description_callback)
skip_due_date_handler = bot.callback_query_handler(func=lambda c: c.data == "skip_due_date")(skip_due_date_callback)
assign_to_creator_handler = bot.callback_query_handler(func=lambda c: c.data == "assign_to_creator")(assign_to_creator_callback)
assign_to_me_handler = bot.callback_query_handler(func=lambda c: c.data == "assign_to_me")(assign_to_me_callback)
choose_user_from_list_handler = bot.callback_query_handler(func=lambda c: c.data == "choose_user_from_list")(choose_user_from_list_callback)
add_subtask_handler = bot.callback_query_handler(func=lambda c: c.data == "add_subtask")(add_subtask_callback)
cancel_subtask_input_handler = bot.callback_query_handler(func=lambda c: c.data == "cancel_subtask_input")(cancel_subtask_input_callback)
clear_subtasks_handler = bot.callback_query_handler(func=lambda c: c.data == "clear_subtasks")(clear_subtasks_callback)
finish_subtasks_handler = bot.callback_query_handler(func=lambda c: c.data == "finish_subtasks")(finish_subtasks_callback)
skip_assignee_handler = bot.callback_query_handler(func=lambda c: c.data == "skip_assignee")(skip_assignee_callback)
choose_assignee_handler = bot.callback_query_handler(func=lambda c: c.data == "choose_assignee")(choose_assignee_callback)
user_page_handler = bot.callback_query_handler(func=lambda c: c.data.startswith("user_page_"))(user_page_callback)
select_user_handler = bot.callback_query_handler(func=lambda c: c.data.startswith("select_user_"))(select_user_callback)
back_to_assignee_selection_handler = bot.callback_query_handler(func=lambda c: c.data == "back_to_assignee_selection")(back_to_assignee_selection_callback)
back_to_assignee_type_handler = bot.callback_query_handler(func=lambda c: c.data == "back_to_assignee_type")(back_to_assignee_type_callback)
cancel_task_creation_handler = bot.callback_query_handler(func=lambda c: c.data == "cancel_task_creation")(cancel_task_creation_callback)
clear_attachments_handler = bot.callback_query_handler(func=lambda c: c.data == "clear_attachments")(clear_attachments_callback)
finish_attachments_handler = bot.callback_query_handler(func=lambda c: c.data == "finish_attachments")(finish_attachments_callback)

# Callback для календаря
calendar_handler = bot.callback_query_handler(func=lambda c: c.data.startswith("calendar_"))(process_calendar_callback)

# Callback для действий с задачами
task_view_handler = bot.callback_query_handler(func=lambda c: c.data.startswith("task_view_"))(task_view_callback)
task_progress_handler = bot.callback_query_handler(func=lambda c: c.data.startswith("task_progress_"))(task_progress_callback)
task_complete_handler = bot.callback_query_handler(func=lambda c: c.data.startswith("task_complete_"))(task_complete_callback)
task_confirm_handler = bot.callback_query_handler(func=lambda c: c.data.startswith("task_confirm_"))(task_confirm_callback)
task_reject_handler = bot.callback_query_handler(func=lambda c: c.data.startswith("task_reject_"))(task_reject_callback)
subtask_toggle_handler = bot.callback_query_handler(func=lambda c: c.data.startswith("subtask_toggle_"))(subtask_toggle_callback)
task_delete_handler = bot.callback_query_handler(func=lambda c: c.data.startswith("task_delete_"))(task_delete_callback)
confirm_delete_handler = bot.callback_query_handler(func=lambda c: c.data.startswith("confirm_delete_"))(confirm_delete_callback)
task_status_handler = bot.callback_query_handler(func=lambda c: c.data.startswith("task_status_"))(task_status_callback)
task_close_handler = bot.callback_query_handler(func=lambda c: c.data.startswith("task_close_"))(task_close_callback)

# Callback для редактирования задач
task_edit_handler = bot.callback_query_handler(func=lambda c: c.data.startswith("task_edit_"))(task_edit_callback)
edit_title_handler = bot.callback_query_handler(func=lambda c: c.data.startswith("edit_title_"))(edit_title_callback)
edit_description_handler = bot.callback_query_handler(func=lambda c: c.data.startswith("edit_description_"))(edit_description_callback)
edit_assignee_handler = bot.callback_query_handler(func=lambda c: c.data.startswith("edit_assignee_"))(edit_assignee_callback)
edit_due_date_handler = bot.callback_query_handler(func=lambda c: c.data.startswith("edit_due_date_"))(edit_due_date_callback)
assignee_page_handler = bot.callback_query_handler(func=lambda c: c.data.startswith("assignee_page_"))(assignee_page_callback)
change_assignee_handler = bot.callback_query_handler(func=lambda c: c.data.startswith("change_assignee_"))(change_assignee_callback)

# Callback для вложений
view_report_attachments_handler = bot.callback_query_handler(func=lambda c: c.data.startswith("view_report_attachments_"))(view_report_attachments_callback)
view_task_attachments_handler = bot.callback_query_handler(func=lambda c: c.data.startswith("view_task_attachments_"))(view_task_attachments_callback)

# Callback для главного меню
tasks_back_handler = bot.callback_query_handler(func=lambda c: c.data == "tasks_back")(tasks_back_callback)
main_menu_handler = bot.callback_query_handler(func=lambda c: c.data == "main_menu")(main_menu_callback)

# Callback для добавления подзадач и изменения статуса задач
add_subtasks_handler = bot.callback_query_handler(func=lambda c: c.data.startswith("add_subtasks_"))(add_subtasks_callback)
reopen_task_handler = bot.callback_query_handler(func=lambda c: c.data.startswith("reopen_task_"))(reopen_task_callback)

# Callback для обучения
start_tutorial_handler = bot.callback_query_handler(func=lambda c: c.data == "start_tutorial")(start_tutorial_callback)
