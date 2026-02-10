import os
import django
import dotenv
from django.db import connection

# Load environment variables
dotenv.load_dotenv()

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dd.settings')
django.setup()

def force_fix_all_tables():
    with connection.cursor() as cursor:
        print("--- ТОТАЛЬНОЕ ИСПРАВЛЕНИЕ КОДИРОВКИ (С ОБХОДОМ FK) ---")
        
        # 1. Отключаем проверку внешних ключей
        print("Отключаю FOREIGN_KEY_CHECKS...")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        
        try:
            # 2. Получаем список всех таблиц
            cursor.execute("SHOW TABLES")
            tables = [row[0] for row in cursor.fetchall()]
            
            for table in tables:
                print(f"Конвертирую таблицу {table}...")
                try:
                    # Устанавливаем кодировку по умолчанию для самой таблицы
                    cursor.execute(f"ALTER TABLE `{table}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
                    # Конвертируем все существующие колонки
                    cursor.execute(f"ALTER TABLE `{table}` CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
                except Exception as e:
                    print(f"Ошибка при работе с таблицей {table}: {e}")

            # 3. Также исправляем кодировку самой базы данных
            cursor.execute("SELECT DATABASE()")
            db_name = cursor.fetchone()[0]
            print(f"Исправляю кодировку базы данных {db_name}...")
            cursor.execute(f"ALTER DATABASE `{db_name}` CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci")

            print("\n✅ УСПЕХ! Все таблицы и база данных переведены на utf8mb4.")
            
        finally:
            # 4. ОБЯЗАТЕЛЬНО включаем проверку внешних ключей обратно
            print("Включаю FOREIGN_KEY_CHECKS...")
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1")

if __name__ == "__main__":
    force_fix_all_tables()
