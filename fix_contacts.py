import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mynewsite.settings')
django.setup()

from newapp.models import User, Admin

# Get the admin we're logged in as (admin@mail.com)
admin = Admin.objects.filter(email='admin@mail.com').first()
if admin:
    print(f"Found admin: {admin.email} (id: {admin.id})")
    
    # Find users with no admin or wrong admin
    users_to_fix = User.objects.exclude(admin_id=admin.id)
    print(f"Users not linked to this admin: {users_to_fix.count()}")
    
    for user in users_to_fix:
        print(f"  - {user.name} ({user.phone_no}) - current admin_id: {user.admin_id}")
    
    # Update all users to link to this admin
    if users_to_fix.count() > 0:
        updated = User.objects.all().update(admin_id=admin.id)
        print(f"\nFixed! Updated {updated} users to admin_id={admin.id}")
else:
    print("Admin admin@mail.com not found")
    
    # Show all admins
    print("\nAll admins:")
    for a in Admin.objects.all():
        print(f"  - {a.email} (id: {a.id})")

# Show all users now
print("\nAll users after fix:")
for u in User.objects.all()[:10]:
    print(f"  - {u.name} ({u.phone_no}) - admin_id: {u.admin_id}")
