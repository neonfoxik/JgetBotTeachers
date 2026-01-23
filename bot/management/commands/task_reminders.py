from django.core.management.base import BaseCommand
from django.utils import timezone
from bot.models import Task, User
from bot import bot, logger
from bot.handlers.utils import format_task_info
from bot.keyboards import get_task_actions_markup

class Command(BaseCommand):
    help = 'Проверка и отправка напоминаний о задачах (однократный запуск через крон)'

    def handle(self, *args, **options):
        now = timezone.now()
        
        # Ищем незавершенные задачи с установленным интервалом
        unfinished_tasks = Task.objects.filter(
            status__in=['active', 'pending_review'],
            notification_interval__isnull=False
        )

        for task in unfinished_tasks:
            try:
                # Определяем точку отсчета для уведомления
                last_notice = task.last_notified_at or task.created_at
                
                # Проверяем, прошел ли интервал (в минутах)
                interval_td = timezone.timedelta(minutes=task.notification_interval)
                
                if now - last_notice >= interval_td:
                    self.send_reminder(task)
                    
                    # Обновляем время последнего уведомления
                    task.last_notified_at = now
                    task.save(update_fields=['last_notified_at'])
                    
            except Exception as e:
                logger.error(f"Ошибка при обработке напоминания для задачи {task.id}: {e}")

    def send_reminder(self, task):
        """Отправляет напоминание всем ответственным за задачу"""
        assignees = task.get_assignees()
        
        reminder_text = f"💡 **НАПОМИНАНИЕ О ЗАДАЧЕ**\n\n{format_task_info(task)}"
        markup = get_task_actions_markup(task.id, task.status, task.report_attachments, False, True)
        
        for user in assignees:
            try:
                bot.send_message(
                    user.telegram_id,
                    reminder_text,
                    reply_markup=markup,
                    parse_mode='Markdown'
                )
                self.stdout.write(self.style.SUCCESS(f"✅ Напоминание по задаче {task.id} отправлено {user.user_name}"))
            except Exception as e:
                logger.error(f"Не удалось отправить напоминание пользователю {user.telegram_id}: {e}")
