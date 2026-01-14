from traceback import format_exc
from asgiref.sync import sync_to_async
from bot.handlers.tasks import (
    start_command, tasks_command, my_created_tasks_command, create_task_command,
    close_task_command, task_progress_command, debug_command, handle_task_creation_messages,
    handle_task_report, skip_description_callback,
    skip_due_date_callback, cancel_task_creation_callback
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
    if request.META.get("CONTENT_TYPE") != "application/json":
        return JsonResponse({"message": "Bad Request"}, status=403)
    json_string = request.body.decode("utf-8")
    update = Update.de_json(json_string)
    try:
        bot.process_new_updates([update])
    except ApiTelegramException as e:
        logger.error(f"Telegram exception. {e} {format_exc()}")
    except ConnectionError as e:
        logger.error(f"Connection error. {e} {format_exc()}")
    except Exception as e:
        if hasattr(settings, 'OWNER_ID') and settings.OWNER_ID:
            try:
                bot.send_message(settings.OWNER_ID, f'Error from index: {e}')
            except Exception as msg_e:
                print(f"Warning: Could not send error notification: {msg_e}")
        logger.error(f"Unhandled exception. {e} {format_exc()}")
    return JsonResponse({"message": "OK"}, status=200)
def register_handlers():
    bot.message_handler(commands=["start"])(start_command)
    bot.message_handler(commands=["tasks"])(tasks_command)
    bot.message_handler(commands=["my_created_tasks"])(my_created_tasks_command)
    bot.message_handler(commands=["create_task"])(create_task_command)
    bot.message_handler(commands=["close_task"])(close_task_command)
    bot.message_handler(commands=["task_progress"])(task_progress_command)
    bot.message_handler(commands=["debug"])(debug_command)
    bot.message_handler(func=lambda message: not message.text.startswith('/') and not message.text.startswith('@'))(handle_task_creation_messages)
    bot.message_handler(content_types=['text', 'photo', 'document'])(handle_task_report)
    bot.callback_query_handler(func=lambda c: c.data == "skip_description")(skip_description_callback)
    bot.callback_query_handler(func=lambda c: c.data == "skip_due_date")(skip_due_date_callback)
    bot.callback_query_handler(func=lambda c: c.data == "cancel_task_creation")(cancel_task_creation_callback)
register_handlers()