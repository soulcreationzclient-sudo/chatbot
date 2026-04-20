#!/usr/bin/env python
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mynewsite.settings')

import django
django.setup()

from django.urls import reverse, NoReverseMatch

print('=== Testing WebChat URL Resolution ===')
print('')

urls_to_test = [
    ('webchat_dashboard', '/webchat/dashboard/'),
    ('webchat_analytics', '/webchat/analytics/'),
    ('webchat_widgets', '/webchat/widgets/'),
    ('webchat_session_detail', '/webchat/session/test-session/'),
]

all_passed = True
for url_name, expected_path in urls_to_test:
    try:
        resolved_path = reverse(url_name)
        if resolved_path == expected_path:
            print(f'✅ {url_name}: {resolved_path}')
        else:
            print(f'⚠️  {url_name}: Expected {expected_path}, got {resolved_path}')
    except NoReverseMatch:
        print(f'❌ {url_name}: URL pattern not found')
        all_passed = False
    except Exception as e:
        print(f'❌ {url_name}: Error - {str(e)}')
        all_passed = False

print('')
if all_passed:
    print('✅ All webchat URLs are properly configured!')
else:
    print('❌ Some URLs have issues')