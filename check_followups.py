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
for fm in FollowUpMessage.objects.all().order_by('step'):
    print(f"  Step {fm.step}: delay={fm.delay_minutes}min msg='{fm.message[:80]}' admin={fm.admin_id} active={fm.is_active} tag={fm.tag_id}")

# Check scheduled follow-ups for this user
print("\n=== Scheduled Follow-Ups for this user ===")
scheduled = ScheduledFollowUp.objects.filter(user__phone_no=phone).order_by('-created_at')[:15]
print(f"Total: {scheduled.count()}")
for s in scheduled:
    fields = {f.name for f in s._meta.get_fields()}
    print(f"  ID={s.id} fields={fields}")
    print(f"    scheduled={getattr(s,'scheduled_at','?')} status={getattr(s,'status','?')} step={getattr(s,'step','?')} created={getattr(s,'created_at','?')}")

# Check recent bot messages (follow-ups)
print("\n=== Recent bot messages for this user ===")
msgs = Message.objects.filter(user_id__phone_no=phone, who='bot').order_by('-id')[:10]
for m in msgs:
    print(f"  ID={m.id} time={m.created_at} text='{m.messages[:120]}'")
