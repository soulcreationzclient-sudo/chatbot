#!/usr/bin/env python
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mynewsite.settings')

import django
django.setup()

from django.urls import reverse, NoReverseMatch

print('=== Testing WebChat URL Resolution ===')
print('')

# Test simple URLs first
simple_urls = [
    'webchat_dashboard',
    'webchat_analytics',
    'webchat_widgets',
]

for url_name in simple_urls:
    try:
        path = reverse(url_name)
        print(f'✅ {url_name}: {path}')
    except NoReverseMatch:
        print(f'❌ {url_name}: URL pattern not found')
    except Exception as e:
        print(f'❌ {url_name}: Error - {str(e)}')

print('')

# Test URLs that require arguments
param_urls = [
    ('webchat_session_detail', ['test-session']),
    ('webchat_messages', ['test-session']),
]

for url_name, args in param_urls:
    try:
        path = reverse(url_name, args=args)
        print(f'✅ {url_name}: {path}')
    except NoReverseMatch:
        print(f'❌ {url_name}: URL pattern not found')
    except Exception as e:
        print(f'❌ {url_name}: Error - {str(e)}')

print('')
print('=== URL Resolution Complete ===')