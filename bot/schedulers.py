from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
from django.utils import timezone
from datetime import timedelta
import logging
from bot import bot
from bot.models import Task, User
from bot.handlers.utils import format_task_info
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

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

scheduler = BackgroundScheduler(jobstores=jobstores, executors=executors, job_defaults=job_defaults, timezone='Europe/Moscow')

def send_daily_reminders():
    logger.info("Starting daily reminders task")
    try:
        users = User.objects.all()
        for user in users:
            try:
                active_tasks = Task.objects.filter(
                    assignee=user,
                    status='active'
                ).order_by('due_date')
                
                if not active_tasks:
                    continue
                
                reminder_text = "👋 **ДОБРОЕ УТРО!**\n\nВот список ваших активных задач на сегодня:\n"
                
                urgent_tasks = []
                today_tasks = []
                upcoming_tasks = []
                no_date_tasks = []
                
                now = timezone.now()
                
                for task in active_tasks:
                    if not task.due_date:
                        no_date_tasks.append(task)
                        continue
                        
                    days_until_due = (task.due_date - now).days
                    if days_until_due < 0:
                        urgent_tasks.append(task)
                    elif days_until_due == 0:
                        today_tasks.append(task)
                    elif days_until_due <= 3:  
                        upcoming_tasks.append(task)
                
                if urgent_tasks:
                    reminder_text += "\n🚨 **ПРОСРОЧЕННЫЕ:**\n"
                    for task in urgent_tasks:
                        reminder_text += f"• {task.title} (был до {timezone.localtime(task.due_date).strftime('%d.%m')})\n"
                
                if today_tasks:
                    reminder_text += "\n📅 **НА СЕГОДНЯ:**\n"
                    for task in today_tasks:
                        reminder_text += f"• {task.title} (до {timezone.localtime(task.due_date).strftime('%H:%M')})\n"
                
                if upcoming_tasks:
                    reminder_text += "\n📆 **СКОРО (3 дня):**\n"
                    for task in upcoming_tasks:
                        reminder_text += f"• {task.title} ({timezone.localtime(task.due_date).strftime('%d.%m')})\n"
                
                if no_date_tasks and not (urgent_tasks or today_tasks):
                    reminder_text += "\n📝 **БЕЗ СРОКА:**\n"
                    for task in no_date_tasks[:5]:
                        reminder_text += f"• {task.title}\n"

                reminder_text += "\n💡 Нажмите кнопку ниже для управления задачами."
                
                markup = InlineKeyboardMarkup()
                markup.add(InlineKeyboardButton("📋 Мои задачи", callback_data="tasks"))
                
                try:
                    bot.send_message(user.telegram_id, reminder_text, parse_mode='Markdown', reply_markup=markup)
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
                reminder_text = f"⏰ **НАПОМИНАНИЕ: СРОК ЗАВТРА**\n\nЗавтра истекает срок выполнения задачи:\n\n"
                reminder_text += format_task_info(task)
                reminder_text += "\n\nПожалуйста, не забудьте завершить её вовремя!"
                
                markup = InlineKeyboardMarkup()
                markup.add(InlineKeyboardButton("📋 Мои задачи", callback_data="tasks"))
                
                bot.send_message(task.assignee.telegram_id, reminder_text, parse_mode='Markdown', reply_markup=markup)
                logger.info(f"Sent due date reminder for task {task.id} to user {task.assignee.telegram_id}")
            except Exception as e:
                logger.error(f"Error processing due date reminder for task {task.id}: {e}")
    except Exception as e:
        logger.error(f"Error in send_due_date_reminders: {e}")

def send_task_specific_reminder(task_id):
    try:
        task = Task.objects.get(id=task_id, status='active')
        reminder_text = f"🔔 **НАПОМИНАНИЕ О ЗАДАЧЕ**\n\nНапоминаем о выполнении задачи:\n\n"
        reminder_text += format_task_info(task)
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📋 Мои задачи", callback_data="tasks"))
        
        bot.send_message(task.assignee.telegram_id, reminder_text, parse_mode='Markdown', reply_markup=markup)
        logger.info(f"Sent personal reminder for task {task.id}")
    except Task.DoesNotExist:
        logger.warning(f"Task {task_id} not found for reminder")
    except Exception as e:
        logger.error(f"Error sending personal reminder for task {task_id}: {e}")

def start_scheduler():
    if scheduler.running:
        logger.info("Scheduler is already running")
        return
    try:
        # Ежедневное напоминание в 08:00
        scheduler.add_job(
            send_daily_reminders,
            trigger=CronTrigger(hour=8, minute=0),
            id='daily_reminders',
            name='Daily task reminders',
            replace_existing=True
        )
        # Напоминание о сроке завтра в 09:00
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
            # Напоминание за 24 часа до срока
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