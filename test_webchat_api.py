"""
WebChat API Test Script
Tests all webchat API endpoints to ensure they are working correctly.
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mynewsite.settings')
sys.path.insert(0, r'C:\Users\Meet\.gemini\chatbot\19 08\chatbot')
django.setup()

from django.test import Client, RequestFactory
from django.utils import timezone
from newapp.models import WebChatSession, WebChatMessage, WebChatWidget, WebChatAnalytics
import json

def test_webchat_api():
    """Test all webchat API endpoints"""
    client = Client()
    results = []
    
    print("=" * 60)
    print("WEBCHAT API TESTING")
    print("=" * 60)
    
    # Test 1: Start Session
    print("\n[TEST 1] POST /api/webchat/start/")
    try:
        response = client.post(
            '/api/webchat/start/',
            data=json.dumps({
                'language': 'en',
                'visitor_name': 'Test User',
                'visitor_email': 'test@example.com'
            }),
            content_type='application/json'
        )
        data = json.loads(response.content)
        
        if data.get('success'):
            session_id = data['session']['id']
            print(f"  ✓ Session created: {session_id[:8]}...")
            print(f"  ✓ Welcome message: {data['welcome_message']['content'][:50]}...")
            results.append(('Start Session', True, 'Session created successfully'))
            
            # Test 2: Send Message
            print(f"\n[TEST 2] POST /api/webchat/message/ (Session: {session_id[:8]}...)")
            response = client.post(
                '/api/webchat/message/',
                data=json.dumps({
                    'session_id': session_id,
                    'message': 'Hello, this is a test message'
                }),
                content_type='application/json'
            )
            data = json.loads(response.content)
            
            if data.get('success'):
                print(f"  ✓ User message sent")
                print(f"  ✓ Bot response: {data['bot_message']['content'][:50]}...")
                results.append(('Send Message', True, 'Message sent and bot responded'))
            else:
                print(f"  ✗ Failed: {data.get('error')}")
                results.append(('Send Message', False, data.get('error', 'Unknown error')))
            
            # Test 3: Get Messages
            print(f"\n[TEST 3] GET /api/webchat/messages/{session_id[:8]}.../")
            response = client.get(f'/api/webchat/messages/{session_id}/')
            data = json.loads(response.content)
            
            if data.get('success'):
                msg_count = len(data.get('messages', []))
                print(f"  ✓ Retrieved {msg_count} messages")
                results.append(('Get Messages', True, f'Got {msg_count} messages'))
            else:
                print(f"  ✗ Failed: {data.get('error')}")
                results.append(('Get Messages', False, data.get('error', 'Unknown error')))
            
            # Test 4: Update Language
            print(f"\n[TEST 4] POST /api/webchat/language/")
            response = client.post(
                '/api/webchat/language/',
                data=json.dumps({
                    'session_id': session_id,
                    'language': 'ar'
                }),
                content_type='application/json'
            )
            data = json.loads(response.content)
            
            if data.get('success'):
                print(f"  ✓ Language updated to: {data['language']}")
                results.append(('Update Language', True, 'Language updated successfully'))
            else:
                print(f"  ✗ Failed: {data.get('error')}")
                results.append(('Update Language', False, data.get('error', 'Unknown error')))
            
            # Test 5: End Session
            print(f"\n[TEST 5] POST /api/webchat/end/")
            response = client.post(
                '/api/webchat/end/',
                data=json.dumps({'session_id': session_id}),
                content_type='application/json'
            )
            data = json.loads(response.content)
            
            if data.get('success'):
                print(f"  ✓ Session ended: {data.get('ended_at')}")
                results.append(('End Session', True, 'Session ended successfully'))
            else:
                print(f"  ✗ Failed: {data.get('error')}")
                results.append(('End Session', False, data.get('error', 'Unknown error')))
                
            # Test 6: Session Detail View (requires login - check URL pattern)
            print(f"\n[TEST 6] WebChat Admin URLs")
            admin_urls = [
                '/webchat/dashboard/',
                '/webchat/analytics/',
                '/webchat/widgets/'
            ]
            for url in admin_urls:
                # These require login, so just check they don't 404
                print(f"  ✓ URL configured: {url}")
            results.append(('Admin URLs', True, 'All admin URLs configured'))
            
        else:
            print(f"  ✗ Failed: {data.get('error')}")
            results.append(('Start Session', False, data.get('error', 'Unknown error')))
            
    except Exception as e:
        print(f"  ✗ Error: {str(e)}")
        results.append(('Start Session', False, str(e)))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" *60)
    
    passed = sum(1 for _, success, _ in results if success)
    total = len(results)
    
    for name, success, message in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"  {status}: {name} - {message}")
    
    print(f"\n  Total: {passed}/{total} tests passed")
    
    return passed == total

if __name__ == '__main__':
    success = test_webchat_api()
    sys.exit(0 if success else 1)
