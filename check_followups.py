"""Check follow-up status for 919327606510"""
import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mynewsite.settings')
sys.path.insert(0, '/home/ubuntu/speedbot')
django.setup()

from newapp.models import Message, FollowUpMessage, ScheduledFollowUp
from django.utils import timezone

phone = '919327606510'

# Check follow-up message configs
print("=== Follow-Up Message Configs ===")
for fm in FollowUpMessage.objects.all().order_by('step_number'):
    print(f"  Step {fm.step_number}: delay={fm.delay_minutes}min msg='{fm.message[:80]}' org={fm.organization_id} admin={fm.admin_id} enabled={fm.is_enabled}")

# Check scheduled follow-ups for this user
print("\n=== Scheduled Follow-Ups for this user ===")
scheduled = ScheduledFollowUp.objects.filter(user__phone_no=phone).order_by('-created_at')[:15]
print(f"Total: {scheduled.count()}")
for s in scheduled:
    print(f"  ID={s.id} step={s.step_number} status={s.status} scheduled={s.scheduled_at} created={s.created_at} sent={getattr(s, 'sent_at', 'N/A')}")

# Check recent bot messages (follow-ups)
print("\n=== Recent bot messages for this user ===")
msgs = Message.objects.filter(user_id__phone_no=phone, who='bot').order_by('-id')[:10]
for m in msgs:
    print(f"  ID={m.id} time={m.created_at} text='{m.messages[:120]}'")
