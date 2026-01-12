from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
from django.utils import timezone
from datetime import timedelta
import logging
from bot import bot
from bot.models import Task, User
from bot.handlers.tasks import format_task_info
logger = logging.getLogger(__name__)
jobstores = {
    'default': MemoryJobStore()
}
executors = {
    'default': ThreadPoolExecutor(max_workers=2)
}
job_defaults = {
    'coalesce': False,
    'max_instances': 3,
    'misfire_grace_time': 30,
}
scheduler = BackgroundScheduler(jobstores=jobstores, executors=executors, job_defaults=job_defaults, timezone='UTC')
def send_daily_reminders():
    logger.info("Starting daily reminders task")
    try:
        users = User.objects.all()
        for user in users:
            try:
                active_tasks = Task.objects.filter(
                    assignee=user,
                    status='active'
                ).exclude(
                    due_date__isnull=True
                ).order_by('due_date')
                if not active_tasks:
                    continue
                reminder_text = ""
                urgent_tasks = []
                today_tasks = []
                upcoming_tasks = []
                now = timezone.now()
                for task in active_tasks:
                    days_until_due = (task.due_date - now).days
                    if days_until_due < 0:
                        urgent_tasks.append(task)
                    elif days_until_due == 0:
                        today_tasks.append(task)
                    elif days_until_due <= 3:  
                        upcoming_tasks.append(task)
                if urgent_tasks:
                    reminder_text += "\n🚨 ПРОСРОЧЕННЫЕ ЗАДАЧИ:\n"
                    for task in urgent_tasks[:5]:  
                        reminder_text += f"• {task.title} (был срок: {task.due_date.strftime('%d.%m.%Y')})\n"
                if today_tasks:
                    reminder_text += "\n📅 ЗАДАЧИ НА СЕГОДНЯ:\n"
                    for task in today_tasks[:5]:
                        reminder_text += f"• {task.title} (до {task.due_date.strftime('%H:%M')})\n"
                if upcoming_tasks:
                    reminder_text += "\n📆 ПРЕДСТОЯЩИЕ ЗАДАЧИ:\n"
                    for task in upcoming_tasks[:5]:
                        days_text = "день" if days_until_due == 1 else "дня" if days_until_due < 5 else "дней"
                        reminder_text += f"• {task.title} (осталось {days_until_due} {days_text})\n"
                reminder_text += "\n"
                reminder_text += "\n\n💡 Используйте /tasks для просмотра всех задач"
                try:
                    bot.send_message(user.telegram_id, reminder_text)
                    logger.info(f"Sent daily reminder to user {user.telegram_id}")
                except Exception as e:
                    logger.error(f"Failed to send reminder to user {user.telegram_id}: {e}")
            except Exception as e:
                logger.error(f"Error processing reminders for user {user.telegram_id}: {e}")
    except Exception as e:
        logger.error(f"Error in send_daily_reminders: {e}")
def send_due_date_reminders():
    logger.info("Starting due date reminders task")
    try:
        tomorrow = timezone.now() + timedelta(days=1)
        tomorrow_start = tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow_end = tomorrow.replace(hour=23, minute=59, second=59, microsecond=999999)
        due_tasks = Task.objects.filter(
            status='active',
            due_date__range=(tomorrow_start, tomorrow_end)
        )
        for task in due_tasks:
            try:
                reminder_text = ""
                try:
                    bot.send_message(task.assignee.telegram_id, reminder_text)
                    logger.info(f"Sent due date reminder for task {task.id} to user {task.assignee.telegram_id}")
                except Exception as e:
                    logger.error(f"Failed to send due date reminder for task {task.id}: {e}")
            except Exception as e:
                logger.error(f"Error processing due date reminder for task {task.id}: {e}")
    except Exception as e:
        logger.error(f"Error in send_due_date_reminders: {e}")
def start_scheduler():
    if scheduler.running:
        logger.info("Scheduler is already running")
        return
    try:
        scheduler.add_job(
            send_daily_reminders,
            trigger=CronTrigger(hour=8, minute=0),  
            id='daily_reminders',
            name='Daily task reminders',
            replace_existing=True
        )
        scheduler.add_job(
            send_due_date_reminders,
            trigger=CronTrigger(hour=9, minute=0),  
            id='due_date_reminders',
            name='Due date reminders',
            replace_existing=True
        )
        scheduler.start()
        logger.info("Scheduler started successfully")
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}")
        raise
def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped")
    else:
        logger.info("Scheduler is not running")
def restart_scheduler():
    stop_scheduler()
    start_scheduler()
def schedule_task_reminder(task):
    try:
        if task.due_date and task.status == 'active':
            reminder_time = task.due_date - timedelta(hours=24)
            if reminder_time > timezone.now():
                scheduler.add_job(
                    send_task_specific_reminder,
                    trigger='date',
                    run_date=reminder_time,
                    args=[task.id],
                    id=f'task_reminder_{task.id}',
                    name=f'Reminder for task {task.id}',
                    replace_existing=True
                )
                logger.info(f"Scheduled reminder for task {task.id} at {reminder_time}")
    except Exception as e:
        logger.error(f"Failed to schedule reminder for task {task.id}: {e}")
def unschedule_task_reminder(task_id):
    try:
        job_id = f'task_reminder_{task_id}'
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
            logger.info(f"Unscheduled reminder for task {task_id}")
    except Exception as e:
        logger.error(f"Failed to unschedule reminder for task {task_id}: {e}")
def send_task_specific_reminder(task_id):
    try:
        task = Task.objects.get(id=task_id, status='active')
        reminder_text = ""
        try:
            bot.send_message(task.assignee.telegram_id, reminder_text)
            logger.info(f"Sent personal reminder for task {task.id}")
        except Exception as e:
            logger.error(f"Failed to send personal reminder for task {task.id}: {e}")
    except Task.DoesNotExist:
        logger.warning(f"Task {task_id} not found for reminder")
    except Exception as e:
        logger.error(f"Error sending personal reminder for task {task_id}: {e}")