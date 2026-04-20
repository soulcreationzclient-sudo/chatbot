import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'mynewsite.settings'
django.setup()
from django.db import connection
c = connection.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE '%webchatwidget%'")
print("Existing indexes:", c.fetchall())
c.execute("DROP INDEX IF EXISTS newapp_webchatwidget_organization_id_name_uniq")
c.execute("DROP INDEX IF EXISTS newapp_webchatwidget_admin_id_name_uniq")
c.execute("DROP INDEX IF EXISTS newapp_webchatwidg_organiza_uniq")
c.execute("DROP INDEX IF EXISTS newapp_webchatwidg_admin_i_uniq")
# Also try the Django-generated names
c.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE '%webchat%'")
remaining = c.fetchall()
print("Remaining webchat indexes:", remaining)
for idx in remaining:
    if 'unique' in idx[0].lower() or 'uniq' in idx[0].lower():
        c.execute(f"DROP INDEX IF EXISTS {idx[0]}")
        print(f"Dropped: {idx[0]}")
print("DONE")
