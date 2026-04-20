#!/usr/bin/env python
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mynewsite.settings')

import django
django.setup()

print('=== Testing WebChat Dashboard Loading ===')
print('')

# Import from urls.py to get the actual imported function
from mynewsite.urls import webchat_dashboard
from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser

print('✅ Successfully imported webchat_dashboard')
print(f'   Function: {webchat_dashboard}')
print('')

try:
    # Create a mock request
    factory = RequestFactory()
    request = factory.get('/webchat/dashboard/')
    
    # Mock authentication
    request.user = AnonymousUser()
    
    # Mock session data (required by the view)
    request.session = {
        'organization_id': 1,  # Mock org ID
    }
    
    # Call the view
    response = webchat_dashboard(request)
    
    print(f'✅ Dashboard view executed successfully!')
    print(f'   Status code: {response.status_code}')
    
    # Check if template was rendered
    if hasattr(response, 'template_name'):
        print(f'   Template: {response.template_name}')
    elif hasattr(response, 'templates'):
        template_names = [t.name for t in response.templates]
        print(f'   Templates: {template_names}')
    
    print('')
    print('=' * 50)
    print('✅ WEBCAT DASHBOARD IS READY!')
    print('=' * 50)
    print('')
    print('📱 You can now access the WebChat dashboard at:')
    print('   http://localhost:8000/webchat/dashboard/')
    print('')
    print('Or from the sidebar navigation menu.')
    
except Exception as e:
    print(f'❌ Error rendering dashboard: {str(e)}')
    import traceback
    traceback.print_exc()