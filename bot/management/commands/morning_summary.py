from django.core.management.base import BaseCommand
from django.utils import timezone
from bot.models import User, Task
from bot import logger
from bot.handlers.utils import send_task_notification
from datetime import timedelta
from django.db.models import Q

class Command(BaseCommand):
    help = 'Отправка утренней сводки задач пользователям'

    def handle(self, *args, **options):
        import pytz
        users = User.objects.all()
        now_utc = timezone.now()
        today_date = now_utc.date()
        
        for user in users:
            try:
                # 1. Проверяем, не отправляли ли уже сегодня
                if user.last_summary_sent_at == today_date:
                    continue
                
                # 2. Определяем текущий час в часовом поясе пользователя
                try:
                    tz = pytz.timezone(user.timezone)
                except:
                    tz = pytz.UTC
                    
                user_now = now_utc.astimezone(tz)
                current_hour = user_now.hour
                
                # 3. Отправляем, если наступил час начала работы (или позже, если пропустили запуск)
                if current_hour >= user.work_start:
                    # Получаем активные задачи пользователя (где он исполнитель напрямую или через роль)
                    user_tasks = Task.objects.filter(status='active').filter(
                        Q(assignee=user) | Q(assigned_role__in=user.roles.all())
                    ).distinct()
                    
                    active_count = user_tasks.count()
                    
                    # Определяем границы недели (до воскресенья включительно)
                    start_of_week = today_date
                    end_of_week = start_of_week + timedelta(days=(6 - start_of_week.weekday()))
                    
                    # Срок истекает на этой неделе
                    due_this_week = user_tasks.filter(
                        due_date__date__range=[start_of_week, end_of_week]
                    ).count()
                    
                    # Просрочены
                    overdue = user_tasks.filter(
                        due_date__lt=now_utc
                    ).count()
                    
                    summary_text = f"☀️ **ДОБРОЕ УТРО!**\n\n"
                    summary_text += f"📊 **Ваша сводка задач на сегодня:**\n"
                    summary_text += f"🔄 Активных задач: {active_count}\n"
                    summary_text += f"📅 Срок истекает на этой неделе: {due_this_week}\n"
                    summary_text += f"⚠️ Просрочены: {overdue}\n\n"
                    summary_text += "Удачного рабочего дня! 💪"
                    
                    # Отправляем уведомление
                    sent = send_task_notification(user.telegram_id, summary_text)
                    
                    if sent:
                        user.last_summary_sent_at = today_date
                        user.save(update_fields=['last_summary_sent_at'])
                        self.stdout.write(self.style.SUCCESS(f"➡️ Сводка отправлена {user.user_name} в {current_hour}:00"))
                
            except Exception as e:
                logger.error(f"Ошибка при обработке сводки для {user.telegram_id}: {e}")
