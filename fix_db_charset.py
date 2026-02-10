import os
import django
import dotenv
from django.db import connection

# Load environment variables
dotenv.load_dotenv()

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dd.settings')
django.setup()

def force_fix_tasks():
    with connection.cursor() as cursor:
        print("--- ТОЧЕЧНОЕ ИСПРАВЛЕНИЕ ТАБЛИЦЫ ЗАДАЧ ---")
        
        # 1. Проверяем текущую кодировку колонки title
        cursor.execute("""
            SELECT COLUMN_NAME, CHARACTER_SET_NAME, COLLATION_NAME 
            FROM information_schema.COLUMNS 
            WHERE TABLE_NAME = 'bot_task' AND COLUMN_NAME = 'title'
        """)
        row = cursor.fetchone()
        if row:
            print(f"Сейчас колонка '{row[0]}' имеет кодировку: {row[1]} (сравнение: {row[2]})")
        
        # 2. Принудительно конвертируем всю таблицу и все её колонки
        print("\nКонвертирую bot_task в utf8mb4...")
        cursor.execute("ALTER TABLE bot_task DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        cursor.execute("ALTER TABLE bot_task CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        
        # 3. На всякий случай пройдемся по другим таблицам, где могут быть эмодзи
        extra_tables = ['bot_subtask', 'bot_taskcomment', 'bot_taskhistory', 'bot_user']
        for table in extra_tables:
            print(f"Конвертирую {table}...")
            cursor.execute(f"ALTER TABLE {table} CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")

        print("\n✅ ГОТОВО! Все текстовые колонки теперь поддерживают эмодзи.")

if __name__ == "__main__":
    force_fix_tasks()
