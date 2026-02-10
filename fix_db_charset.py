import os
import django
import dotenv
from django.db import connection
from django.conf import settings

# Load environment variables
dotenv.load_dotenv()

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dd.settings')
django.setup()

def check_and_fix():
    engine = settings.DATABASES['default']['ENGINE']
    if 'mysql' not in engine:
        print(f"Current engine is {engine}. This script is only for MySQL.")
        return

    with connection.cursor() as cursor:
        # Check current connection charset
        cursor.execute("SHOW VARIABLES LIKE 'character_set_connection'")
        print(f"Current connection charset: {cursor.fetchone()[1]}")

        # Get database name
        cursor.execute("SELECT DATABASE()")
        db_name = cursor.fetchone()[0]
        
        print(f"Working on database: {db_name}")
        
        # 1. Fix Database
        print(f"Converting database {db_name}...")
        cursor.execute(f"ALTER DATABASE `{db_name}` CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci")
        
        # 2. Fix Tables
        cursor.execute("SHOW TABLES")
        tables = [row[0] for row in cursor.fetchall()]
        
        for table in tables:
            print(f"Converting table {table}...")
            try:
                # CONVERT TO changes the table AND all its columns
                cursor.execute(f"ALTER TABLE `{table}` CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            except Exception as e:
                print(f"Error converting table {table}: {e}")
                
        print("\nSUCCESS! Database and all tables/columns converted to utf8mb4.")
        print("IMPORTANT: You MUST restart your bot process to apply changes in settings.py.")

if __name__ == "__main__":
    try:
        check_and_fix()
    except Exception as e:
        print(f"Critical error: {e}")
