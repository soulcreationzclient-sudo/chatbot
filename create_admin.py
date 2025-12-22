import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'mynewsite.settings'

import django
django.setup()

from newapp.models import Admin

# Create admin user
admin, created = Admin.objects.get_or_create(
    email='admin@test.com',
    defaults={
        'password': 'admin123',
        'whatsapp_phone_id': '',
        'whatsapp_token': '',
        'pinecone_token': '',
        'display_phone_no': '',
        'goolgle_calendar': ''
    }
)

if created:
    print('Admin created with email: admin@test.com, password: admin123')
else:
    print('Admin already exists with email: admin@test.com')
