#!/usr/bin/env python
"""Test webchat URL resolution."""

import os
import sys

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mynewsite.settings')

import django
django.setup()

from django.urls import reverse

print("=" * 60)
print("Testing WebChat URL Resolution")
print("=" * 60)
print()

try:
    print("Testing Admin URLs:")
    print(f"  webchat_dashboard:        {reverse('webchat_dashboard')}")
    print(f"  webchat_analytics:        {reverse('webchat_analytics')}")
    print(f"  webchat_widgets:          {reverse('webchat_widgets')}")
    print(f"  webchat_session_detail:   {reverse('webchat_session_detail', args=['test-session'])}")
    print()
    print("Testing API URLs:")
    print(f"  webchat_start:            {reverse('webchat_start')}")
    print(f"  webchat_message:          {reverse('webchat_message')}")
    print(f"  webchat_messages:         {reverse('webchat_messages', args=['test-session'])}")
    print(f"  webchat_end:              {reverse('webchat_end')}")
    print(f"  webchat_feedback:         {reverse('webchat_feedback')}")
    print(f"  webchat_language:         {reverse('webchat_language')}")
    print()
    print("✅ All webchat URLs resolved successfully!")
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
