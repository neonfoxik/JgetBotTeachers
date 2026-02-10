import os
import django
import dotenv
from django.db import connection

# Load environment variables
dotenv.load_dotenv()

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dd.settings')
django.setup()

def fix_charset():
    with connection.cursor() as cursor:
        # Get database name
        cursor.execute("SELECT DATABASE()")
        db_name = cursor.fetchone()[0]
        
        print(f"fixing database: {db_name}")
        
        # Change database collation
        print(f"Converting database {db_name} to utf8mb4...")
        cursor.execute(f"ALTER DATABASE `{db_name}` CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci")
        
        # Get all tables
        cursor.execute("SHOW TABLES")
        tables = [row[0] for row in cursor.fetchall()]
        
        for table in tables:
            print(f"Converting table {table} to utf8mb4...")
            try:
                cursor.execute(f"ALTER TABLE `{table}` CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            except Exception as e:
                print(f"Error converting table {table}: {e}")
                
        print("Success! All tables converted.")

if __name__ == "__main__":
    if os.getenv('LOCAL', 'True').lower() == 'true':
        print("LOCAL=True. This script is intended for MySQL databases. Skipping.")
    else:
        try:
            fix_charset()
        except Exception as e:
            print(f"Critical error: {e}")
