import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mynewsite.settings')
django.setup()

from newapp.models import Admin

def check():
    for admin in Admin.objects.all():
        print(f"ID: {admin.id}, Email: {admin.email}")
        print(f"Phone ID: '{admin.whatsapp_phone_id}'")
        print(f"Token: '{admin.whatsapp_token[:10]}...'")
        print(f"OpenAI Key: '{admin.openai_api_key[:10]}...'")

if __name__ == "__main__":
    check()
