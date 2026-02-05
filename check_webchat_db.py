import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mynewsite.settings')
django.setup()

from django.db import connection

cursor = connection.cursor()

# List all tables containing 'webchat'
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'webchat%'")
tables = cursor.fetchall()

print("=== WebChat Database Tables Check ===")
print("")

if tables:
    print("Webchat tables found:")
    for table in tables:
        table_name = table[0]
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"  ✅ {table_name}: {count} records")
        except:
            print(f"  ✅ {table_name}: exists (could not count)")
else:
    print("No webchat tables found in database!")
    print("")
    print("This means the migration has NOT been applied yet.")
    print("Tables that should exist:")
    print("  - webchat_sessions")
    print("  - webchat_messages")
    print("  - webchat_widgets")
    print("  - webchat_analytics")
