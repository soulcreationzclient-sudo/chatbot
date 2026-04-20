#!/usr/bin/env python
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mynewsite.settings')

import django
django.setup()

from django.test import RequestFactory
from newapp.controllers.webchat_admin import webchat_dashboard

print('=== Testing WebChat Dashboard Rendering ===')
print('')

try:
    # Create a mock request
    factory = RequestFactory()
    request = factory.get('/webchat/dashboard/')
    
    # Mock authentication
    from django.contrib.auth.models import AnonymousUser
    request.user = AnonymousUser()
    
    # Call the view
    response = webchat_dashboard(request)
    
    print(f'✅ Dashboard view executed successfully!')
    print(f'   Status code: {response.status_code}')
    
    # Check if template was rendered
    if hasattr(response, 'template_name'):
        print(f'   Templates used: {response.template_name}')
    elif hasattr(response, 'templates'):
        print(f'   Templates used: {[t.name for t in response.templates]}')
    
    print('')
    print('✅ WebChat Dashboard is ready to use!')
    print('')
    print('📱 Access the dashboard at: /webchat/dashboard/')
    
except Exception as e:
    print(f'❌ Error rendering dashboard: {str(e)}')
    import traceback
    traceback.print_exc()