import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mynewsite.settings')
django.setup()

from newapp.models import OrganizationUser

sa = OrganizationUser.objects.filter(role__name='super_admin').first()
if sa:
    print(f"Username: {sa.user.username}")
    print(f"Email: {sa.user.email}")
else:
    print("No Super Admin found")
