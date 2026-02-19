"""Check image assets and recent bot messages on the server"""
import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mynewsite.settings')
sys.path.insert(0, '/home/ubuntu/speedbot')
django.setup()

from newapp.models import ImageAsset, Message
from django.utils import timezone

print("=== Image Assets ===")
assets = ImageAsset.objects.all()
print(f"Total: {assets.count()}")
for a in assets:
    print(f"  ID={a.id} Name={a.name} File={a.image} Admin={a.admin_id} Org={a.organization_id}")

print("\n=== Last bot message containing text (most recent) ===")
cutoff = timezone.now() - timezone.timedelta(minutes=30)
msgs = Message.objects.filter(who='bot', created_at__gte=cutoff).order_by('-id')[:5]
for m in msgs:
    print(f"  ID={m.id} Phone={m.user_id.phone_no} Time={m.created_at}")
    print(f"    Text: {m.messages[:200]}")

print("\n=== Check debug_log for image processing ===")
try:
    with open('/home/ubuntu/speedbot/debug_log.txt', 'r') as f:
        lines = f.readlines()
    # Find lines with image-related content
    img_lines = [l.strip() for l in lines if 'image' in l.lower() or 'ImageTag' in l or 'Images sent' in l]
    print(f"Image-related log lines: {len(img_lines)}")
    for l in img_lines[-10:]:
        print(f"  {l}")
except Exception as e:
    print(f"  Error reading debug_log: {e}")
