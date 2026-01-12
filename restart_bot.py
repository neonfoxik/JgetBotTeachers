import os
import sys
import subprocess
import time
def run_command(cmd):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Команда превысила время ожидания"
def main():
    print("🔄 Перезапуск бота...")
    print("1. Останавливаем бота...")
    success, stdout, stderr = run_command("python manage.py stop_bot")
    if success:
        print("✅ Бот остановлен")
    else:
        print(f"⚠️ Не удалось остановить бота: {stderr}")
    time.sleep(2)
    print("2. Запускаем бота...")
    success, stdout, stderr = run_command("python manage.py run_bot --remove-webhook")
    if success:
        print("✅ Бот запущен")
        print(stdout)
    else:
        print(f"❌ Ошибка запуска бота: {stderr}")
        print(stdout)
if __name__ == '__main__':
    main()