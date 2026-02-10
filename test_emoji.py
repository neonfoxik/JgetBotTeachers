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
    
    from django.db import connection
    from bot.models import User
    
    emoji_text = "Тест эмодзи 🥺🤯😳👌"
    
    try:
        # 1. Сначала проверяем через прямой SQL запрос (самый надежный способ проверить кодировку)
        print("Шаг 1: Тест прямого SQL запроса...")
        with connection.cursor() as cursor:
            cursor.execute("SELECT %s as test", [emoji_text])
            result = cursor.fetchone()
            if result[0] == emoji_text:
                print("✅ SQL-соединение поддерживает эмодзи!")
            else:
                print("❌ SQL-соединение вернуло битые данные.")

        # 2. Пробуем создать/обновить объект через Django
        print("\nШаг 2: Тест через модели Django...")
        
        # Пробуем найти или создать тестового пользователя
        user, created = User.objects.get_or_create(
            telegram_id="test_emoji_user",
            defaults={"user_name": "EmojiTester", "first_name": "Test"}
        )
        
        # Пробуем сохранить эмодзи в поле first_name
        user.first_name = f"Улыбка {emoji_text}"
        user.save()
        
        print(f"✅ УСПЕХ! Данные с эмодзи успешно сохранены в таблицу.")
        
        # Удаляем тестового пользователя
        if created:
            user.delete()
            print("Тестовые данные очищены.")

    except Exception as e:
        print("\n❌ ОШИБКА:")
        print(str(e))
        
        if "1366" in str(e):
            print("\nПричина: База данных или соединение все еще НЕ поддерживают utf8mb4.")
            print("Требуется:")
            print("1. Перезагрузить бота (процесс Python).")
            print("2. Убедиться, что на сервере в .env стоит LOCAL=False.")
        else:
            print("\nЭто техническая ошибка валидации или структуры, а не кодировки.")

if __name__ == "__main__":
    test_emoji_insertion()

if __name__ == "__main__":
    test_emoji_insertion()
