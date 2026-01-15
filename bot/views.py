from traceback import format_exc
from asgiref.sync import sync_to_async
from bot.handlers import (
    start_command, tasks_command, my_created_tasks_command,
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
def register_handlers():
    logger.info("Регистрация обработчиков бота...")
    try:
        bot.message_handler(commands=["start"])(start_command)
        logger.info("Обработчик /start зарегистрирован")
        bot.message_handler(commands=["tasks"])(tasks_command)
        logger.info("Обработчик /tasks зарегистрирован")
        bot.message_handler(commands=["my_created_tasks"])(my_created_tasks_command)
        bot.message_handler(commands=["close_task"])(close_task_command)
        bot.message_handler(commands=["task_progress"])(task_progress_command)
        bot.message_handler(commands=["debug"])(debug_command)
        bot.message_handler(func=lambda message: not message.text.startswith('/') and not message.text.startswith('@'))(handle_task_creation_messages)
        bot.message_handler(content_types=['text', 'photo', 'document'])(handle_task_report)
        bot.callback_query_handler(func=lambda c: c.data == "skip_description")(skip_description_callback)
        bot.callback_query_handler(func=lambda c: c.data == "skip_due_date")(skip_due_date_callback)
        bot.callback_query_handler(func=lambda c: c.data == "cancel_task_creation")(cancel_task_creation_callback)
        logger.info("Все обработчики успешно зарегистрированы")
    except Exception as e:
        logger.error(f"Ошибка при регистрации обработчиков: {e}")
        import traceback
        logger.error(traceback.format_exc())

# Регистрируем обработчики при загрузке модуля
register_handlers()