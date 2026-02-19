"""Check recent messages for phone 919327606510"""
import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mynewsite.settings')
sys.path.insert(0, '/home/ubuntu/speedbot')
django.setup()

from newapp.models import Message

msgs = Message.objects.filter(user_id__phone_no='919327606510').order_by('-id')[:10]
for m in msgs:
    print(f"ID={m.id} who={m.who} time={m.created_at}")
    print(f"  text: {m.messages[:300]}")
    print()
