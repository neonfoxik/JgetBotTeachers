from django.core.management.base import BaseCommand
import os
import signal
import time
class Command(BaseCommand):
    help = 'Остановка бота, запущенного в режиме polling'
    def handle(self, *args, **options):
        pid_file = '/tmp/bot_polling.pid'
        if not os.path.exists(pid_file):
            self.stderr.write('❌ PID файл не найден. Бот, возможно, не запущен.')
            return
        try:
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())
            self.stdout.write(f'🛑 Останавливаем бота (PID: {pid})...')
            os.kill(pid, signal.SIGTERM)
            time.sleep(3)
            try:
                os.kill(pid, 0)
                self.stderr.write('⚠️ Процесс все еще работает. Принудительно завершаем...')
                os.kill(pid, signal.SIGKILL)
                time.sleep(1)
            except OSError:
                pass  
            if os.path.exists(pid_file):
                os.remove(pid_file)
            self.stdout.write('✅ Бот остановлен')
        except (ValueError, OSError) as e:
            self.stderr.write(f'❌ Ошибка при остановке бота: {e}')
            if os.path.exists(pid_file):
                try:
                    os.remove(pid_file)
                except OSError:
                    pass