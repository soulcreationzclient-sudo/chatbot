import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mynewsite.settings')
django.setup()

from newapp.models import ExternalAPI, Admin

def check():
    for admin in Admin.objects.all():
        print(f"Admin: {admin.email} (ID: {admin.id})")
        tools = ExternalAPI.objects.filter(admin=admin)
        print(f"Tools Count: {tools.count()}")
        for t in tools:
            print(f" - {t.name}: {t.description}")

if __name__ == "__main__":
    check()
