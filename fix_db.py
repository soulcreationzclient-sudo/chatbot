import os, sys, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'mynewsite.settings'
sys.path.insert(0, '/home/ubuntu/speedbot')
django.setup()
from django.db import connection
from django.apps import apps

c = connection.cursor()

# Get all models in newapp
app_models = apps.get_app_config('newapp').get_models()

for model in app_models:
    table = model._meta.db_table
    
    # Check if table exists
    tables = connection.introspection.table_names()
    if table not in tables:
        from django.db import connections
        with connections['default'].schema_editor() as schema_editor:
            try:
                schema_editor.create_model(model)
                print(f'CREATED TABLE: {table}')
            except Exception as e:
                print(f'ERROR creating {table}: {e}')
        continue
    
    # Table exists - check for missing columns
    c.execute('PRAGMA table_info("' + table + '")')
    existing_cols = {row[1] for row in c.fetchall()}
    
    for field in model._meta.local_fields:
        col_name = field.column
        if col_name not in existing_cols:
            col_type = field.db_type(connection)
            if col_type is None:
                continue
            null_str = 'NULL' if field.null else 'NOT NULL'
            default_str = ''
            if field.has_default():
                d = field.default
                if callable(d):
                    default_str = ''
                elif d is False or d == 0:
                    default_str = 'DEFAULT 0'
                elif d is True or d == 1:
                    default_str = 'DEFAULT 1'
                elif isinstance(d, str):
                    default_str = "DEFAULT '" + d.replace("'", "''") + "'"
                elif isinstance(d, (int, float)):
                    default_str = 'DEFAULT ' + str(d)
            
            # SQLite requires NULL or DEFAULT for ADD COLUMN
            if 'NOT NULL' in null_str and not default_str:
                default_str = "DEFAULT ''"
            
            sql = 'ALTER TABLE "' + table + '" ADD COLUMN "' + col_name + '" ' + col_type + ' ' + null_str + ' ' + default_str
            try:
                c.execute(sql)
                print('ADDED: ' + table + '.' + col_name + ' (' + col_type + ')')
            except Exception as e:
                print('ERROR ' + table + '.' + col_name + ': ' + str(e))

# Restart gunicorn
import subprocess
subprocess.run(['pkill', '-HUP', 'gunicorn'], capture_output=True)
print('Gunicorn reloaded')
print('ALL DONE')
