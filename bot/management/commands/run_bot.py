from django.core.management.base import BaseCommand
from django.conf import settings
import telebot
from bot import bot
import os
import signal
import sys
import atexit
class Command(BaseCommand):
    help = 'Запуск бота в режиме polling'
    def __init__(self):
        super().__init__()
        self.pid_file = '/tmp/bot_polling.pid'
    def add_arguments(self, parser):
        parser.add_argument(
            '--remove-webhook',
            action='store_true',
            help='Удалить webhook перед запуском polling',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Принудительно запустить бота, игнорируя существующий PID файл',
        )
    def check_existing_process(self):
        if os.path.exists(self.pid_file):
            try:
                with open(self.pid_file, 'r') as f:
                    pid = int(f.read().strip())
                os.kill(pid, 0)  
                return True, pid
            except (OSError, ValueError):
                try:
                    os.remove(self.pid_file)
                except OSError:
                    pass
                return False, None
        return False, None
    def create_pid_file(self):
        with open(self.pid_file, 'w') as f:
            f.write(str(os.getpid()))
    def remove_pid_file(self):
        try:
            if os.path.exists(self.pid_file):
                os.remove(self.pid_file)
        except OSError:
            pass
    def signal_handler(self, signum, frame):
        self.stdout.write('\n🛑 Получен сигнал остановки, завершаем работу...')
        self.remove_pid_file()
        sys.exit(0)
    def handle(self, *args, **options):
        exists, pid = self.check_existing_process()
        if exists and not options['force']:
            self.stderr.write(
                f'❌ Бот уже запущен (PID: {pid}). '
                'Используйте --force для принудительного запуска или остановите существующий процесс.'
            )
            sys.exit(1)
        if exists and options['force']:
            self.stdout.write(f'⚠️ Останавливаем существующий процесс (PID: {pid})...')
            try:
                os.kill(pid, signal.SIGTERM)
                import time
                time.sleep(2)
            except OSError:
                pass
        if options['remove_webhook']:
            self.stdout.write('🚀 Запуск бота в режиме polling...')
            try:
                bot.delete_webhook()
                self.stdout.write('✅ Webhook удален')
            except Exception as e:
                self.stdout.write(f'⚠️ Не удалось удалить webhook: {e}')
        self.create_pid_file()
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        atexit.register(self.remove_pid_file)
        self.stdout.write('📡 Бот запущен в режиме polling')
        self.stdout.write('Нажмите Ctrl+C для остановки')
        self.stdout.write(f'PID файла: {self.pid_file}')
        try:
            bot.polling(non_stop=True, interval=0)
        except KeyboardInterrupt:
            self.stdout.write('\n🛑 Бот остановлен пользователем')
        except Exception as e:
            self.stderr.write(f'❌ Ошибка при работе бота: {e}')
        finally:
            self.remove_pid_file()