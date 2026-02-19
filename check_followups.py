"""Check follow-up status on the server. Run via: python check_followups.py"""
import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mynewsite.settings')
sys.path.insert(0, '/home/ubuntu/speedbot')
django.setup()

from newapp.models import ScheduledFollowUp, Message
from django.utils import timezone

print("=== Last 10 Scheduled Follow-Ups ===")
for f in ScheduledFollowUp.objects.all().order_by('-id')[:10]:
    print(f"  ID={f.id} Step={f.step} Status={f.status} Phone={f.user.phone_no} Scheduled={f.scheduled_for} Sent={f.sent_at}")

print("\n=== Recent Bot Messages (last 30 min) ===")
cutoff = timezone.now() - timezone.timedelta(minutes=30)
for m in Message.objects.filter(who='bot', created_at__gte=cutoff).order_by('-id')[:10]:
    print(f"  ID={m.id} Phone={m.user_id.phone_no} Time={m.created_at} Msg={m.messages[:80]}")

print("\n=== Pending Follow-Ups ===")
pending = ScheduledFollowUp.objects.filter(status='pending')
print(f"  Count: {pending.count()}")
for p in pending:
    print(f"  ID={p.id} Step={p.step} Phone={p.user.phone_no} Due={p.scheduled_for}")
