"""Check which bot/org handles which phone number"""
import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mynewsite.settings')
sys.path.insert(0, '/home/ubuntu/speedbot')
django.setup()

from newapp.models import User, AdminCustomUser, Organization, ImageAsset

# Check who owns 919327606510
users = User.objects.filter(phone_no__contains='919327606510')
for u in users:
    print(f"User: {u.phone_no} admin={u.admin_id} org={u.organization}")
    
# Check JamYou admin/org
print("\n=== All Organizations ===")
for o in Organization.objects.all():
    print(f"  Org ID={o.id} Name={o.name}")

print("\n=== All Admins ===")
for a in AdminCustomUser.objects.all():
    print(f"  Admin ID={a.id} Phone={a.phone_no} Org={a.organization_id}")

print("\n=== Image Assets with paths ===")
for ia in ImageAsset.objects.all():
    exists = os.path.exists(ia.image.path) if ia.image else False
    print(f"  ID={ia.id} Name={ia.name} Org={ia.organization_id} Admin={ia.admin_id} Path={ia.image} Exists={exists}")
