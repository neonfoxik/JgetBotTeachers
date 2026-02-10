import os
import django
import dotenv

# Load environment variables
dotenv.load_dotenv()

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dd.settings')
django.setup()

from bot.models import Task, User

def test_emoji_insertion():
    print("--- Проверка поддержки эмодзи ---")
    
    # 1. Проверяем настройки БД
    from django.conf import settings
    db_config = settings.DATABASES['default']
    print(f"Engine: {db_config['ENGINE']}")
    print(f"Charset in OPTIONS: {db_config.get('OPTIONS', {}).get('charset')}")
    
    try:
        # 2. Берем любого пользователя или создаем тестового
        user = User.objects.first()
        if not user:
            print("Ошибка: В базе нет пользователей. Сначала зарегистрируйтесь в боте.")
            return

        # 3. Пробуем создать задачу с эмодзи
        emoji_text = "Тест эмодзи 🥺🤯😳👌"
        print(f"Пробую создать задачу с текстом: {emoji_text}")
        
        task = Task.objects.create(
            title=f"Тест {emoji_text}",
            description="Проверка кодировки",
            creator=user,
            assigned_role=None, # Или укажите роль, если нужно
            assignee=user
        )
        print(f"✅ УСПЕХ! Задача #{task.id} создана с эмодзи.")
        
        # Удаляем тестовую задачу
        task.delete()
        print("Тестовая задача удалена.")
        
    except Exception as e:
        print("\n❌ ОШИБКА ПРИ ТЕСТЕ:")
        print(str(e))
        
        if "1366" in str(e):
            print("\nПричина: База данных все еще отклоняет 4-байтовые символы.")
            print("Возможные решения:")
            print("1. Убедитесь, что вы ПЕРЕЗАПУСТИЛИ бота после изменения settings.py.")
            print("2. Если вы на хостинге, проверьте в phpMyAdmin, что СРАВНЕНИЕ (Collation) колонки 'title' именно utf8mb4_unicode_ci.")
            print("3. Попробуйте еще раз запустить: python fix_db_charset.py")

if __name__ == "__main__":
    test_emoji_insertion()
