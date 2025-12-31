
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mynewsite.settings')
django.setup()

from django.contrib.auth.models import User

try:
    if not User.objects.filter(username='admin').exists():
        User.objects.create_superuser('admin', 'admin@example.com', 'password123')
        print("✅ Superuser 'admin' created with password 'password123'")
    else:
        u = User.objects.get(username='admin')
        u.set_password('password123')
        u.save()
        print("✅ Superuser 'admin' password reset to 'password123'")
except Exception as e:
    print(f"Error: {e}")
