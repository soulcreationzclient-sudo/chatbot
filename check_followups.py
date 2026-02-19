"""Check follow-up status for 919327606510"""
import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mynewsite.settings')
sys.path.insert(0, '/home/ubuntu/speedbot')
django.setup()

from newapp.models import Message, FollowUpMessage, PendingFollowUp
from django.utils import timezone

phone = '919327606510'

# Check follow-up message configs
print("=== Follow-Up Message Configs ===")
for fm in FollowUpMessage.objects.all().order_by('step_number'):
    print(f"  Step {fm.step_number}: delay={fm.delay_minutes}min msg='{fm.message[:80]}' org={fm.organization_id} admin={fm.admin_id}")

# Check pending follow-ups
print("\n=== Pending Follow-Ups for this user ===")
pending = PendingFollowUp.objects.filter(user__phone_no=phone).order_by('-created_at')
print(f"Total: {pending.count()}")
for p in pending:
    print(f"  ID={p.id} step={p.step_number} status={p.status} scheduled={p.scheduled_at} created={p.created_at}")

# Check ALL pending follow-ups
print("\n=== ALL Pending Follow-Ups (recent) ===")
all_pending = PendingFollowUp.objects.all().order_by('-created_at')[:20]
for p in all_pending:
    print(f"  ID={p.id} user={p.user.phone_no} step={p.step_number} status={p.status} scheduled={p.scheduled_at}")

# Check recent bot messages (follow-ups)
print("\n=== Recent bot messages for this user ===")
msgs = Message.objects.filter(user_id__phone_no=phone, who='bot').order_by('-id')[:10]
for m in msgs:
    print(f"  ID={m.id} time={m.created_at} text='{m.messages[:100]}'")
