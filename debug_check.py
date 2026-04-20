import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'mynewsite.settings'
django.setup()
from newapp.models import Message, User

# Check user state
u = User.objects.filter(phone_no__contains='919327606510').first()
if u:
    print(f"User: id={u.id} name={u.name} bot_enabled={u.bot_enabled} inbox={u.is_in_inbox}")
    msgs = Message.objects.filter(user_id=u).order_by('-id')[:10]
    for m in msgs:
        print(f"  {m.id} | {m.who:5} | {m.messages[:80]} | {m.created_at}")
else:
    print("User not found")

# Check prompts
from newapp.models import ChatGPTPrompt, Organization
org = Organization.objects.first()
if org:
    prompts = ChatGPTPrompt.objects.filter(organization=org).order_by('-is_default', '-updated_at')
    print(f"\nPrompts for org '{org.name}':")
    for p in prompts:
        print(f"  id={p.id} name='{p.name}' default={p.is_default} model={p.gpt_model} updated={p.updated_at}")
