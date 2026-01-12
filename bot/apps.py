from django.apps import AppConfig
import os
class BotConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'bot'
    def ready(self):
        if os.getenv('RUN_SCHEDULER') == 'true':
            try:
                from .schedulers import start_scheduler
                start_scheduler()
                print("Task scheduler started successfully")
            except Exception as e:
                print(f"Failed to start task scheduler: {e}")