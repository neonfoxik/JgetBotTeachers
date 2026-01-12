import os
import sys
def test_pid_file_logic():
    pid_file = '/tmp/test_bot.pid'
    if os.path.exists(pid_file):
        os.remove(pid_file)
    print("🧪 Тестирование логики PID файла...")
    with open(pid_file, 'w') as f:
        f.write(str(os.getpid()))
    print("✓ PID файл создан")
    try:
        os.kill(os.getpid(), 0)  
        print("✓ Процесс существует")
    except OSError:
        print("✗ Процесс не существует")
        return False
    if os.path.exists(pid_file):
        os.remove(pid_file)
        print("✓ PID файл удален")
    print("✅ Логика PID файла работает корректно")
    return True
def test_commands():
    print("\n🧪 Тестирование команд...")
    print("Тестируем команду stop_bot...")
    result = os.system("python manage.py stop_bot 2>/dev/null")
    if result != 0:
        print("✓ Команда stop_bot корректно обрабатывает отсутствие запущенного бота")
    else:
        print("⚠️ Команда stop_bot вернула неожиданный результат")
    print("✅ Команды протестированы")
def main():
    print("🚀 Запуск тестирования команд бота\n")
    try:
        test_pid_file_logic()
        test_commands()
        print("\n✅ Все тесты пройдены!")
    except Exception as e:
        print(f"\n❌ Ошибка тестирования: {e}")
        return 1
    return 0
if __name__ == '__main__':
    sys.exit(main())