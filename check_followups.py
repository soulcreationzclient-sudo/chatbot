"""Check follow-up config ownership"""
import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mynewsite.settings')
sys.path.insert(0, '/home/ubuntu/speedbot')
django.setup()

from newapp.models import FollowUpMessage, Admin, Organization, User

print("=== FollowUpMessages ===")
for f in FollowUpMessage.objects.all():
    print(f"  ID={f.id} step={f.step} admin_id={f.admin_id} tag={f.tag_id} active={f.is_active} delay={f.delay_minutes} msg='{f.message[:80]}'")

print("\n=== Admins ===")
for a in Admin.objects.all():
    print(f"  ID={a.id} phone_id={a.whatsapp_phone_id}")

print("\n=== Orgs ===")
for o in Organization.objects.all():
    print(f"  ID={o.id} name={o.name} phone_id={o.whatsapp_phone_id}")

print("\n=== User 919327606510 ===")
u = User.objects.filter(phone_no='919327606510').first()
if u:
    print(f"  admin_id={u.admin_id_id} org_id={u.organization_id}")
    # Simulate the lookup
    admin = u.admin_id
    org = u.organization
    print(f"  admin obj={admin}")
    print(f"  org obj={org}")
    if not admin and org and org.whatsapp_phone_id:
        matched = Admin.objects.filter(whatsapp_phone_id=org.whatsapp_phone_id).first()
        print(f"  fallback matched admin={matched} (id={matched.id if matched else None})")
        if matched:
            configs = FollowUpMessage.objects.filter(admin=matched, is_active=True)
            print(f"  configs found: {configs.count()}")
            for c in configs:
                print(f"    step={c.step} msg='{c.message[:80]}' delay={c.delay_minutes}")
