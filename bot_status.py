import os
import signal
import time
def check_bot_status():
    pid_file = '/tmp/bot_polling.pid'
    if not os.path.exists(pid_file):
        print("❌ Бот не запущен (PID файл не найден)")
        return False
    try:
        with open(pid_file, 'r') as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)
        print(f"✅ Бот запущен (PID: {pid})")
        return True
    except (OSError, ValueError) as e:
        print(f"❌ Бот не запущен (PID файл поврежден: {e})")
        try:
            os.remove(pid_file)
        except OSError:
            pass
        return False
def main():
    print("📊 Проверка статуса бота\n")
    running = check_bot_status()
    if running:
        print("\n💡 Для остановки бота используйте:")
        print("   python manage.py stop_bot")
        print("   или python restart_bot.py")
    else:
        print("\n💡 Для запуска бота используйте:")
        print("   python manage.py run_bot --remove-webhook")
        print("   или python restart_bot.py")
if __name__ == '__main__':
    main()