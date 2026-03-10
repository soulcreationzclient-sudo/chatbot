"""
Calendly Integration API Views
Handles connect/disconnect and follow-up settings for Calendly integration.
"""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import json
import requests

from .models import Admin


@csrf_exempt
@require_POST
def connect_calendly(request):
    """
    Connect Calendly integration by saving the Personal Access Token
    and scheduling URL.
    """
    try:
        admin_id = request.session.get('admin_id')
        org_id = request.session.get('organization_id')
        admin = None
        org = None
        
        if org_id:
            from .models import Organization
            org = Organization.objects.filter(id=org_id).first()
        
        if admin_id:
            admin = Admin.objects.filter(id=admin_id).first()
        elif org and org.whatsapp_phone_id:
            admin = Admin.objects.filter(whatsapp_phone_id=org.whatsapp_phone_id).first()
        
        if not admin and not org:
            return JsonResponse({'success': False, 'error': 'Not authenticated'}, status=401)
        
        data = json.loads(request.body)
        calendly_token = data.get('calendly_token', '').strip()
        scheduling_url = data.get('scheduling_url', '').strip()
        
        if not calendly_token:
            return JsonResponse({'success': False, 'error': 'Calendly token is required'}, status=400)
        
        if not scheduling_url:
            return JsonResponse({'success': False, 'error': 'Scheduling URL is required'}, status=400)
        
        # Validate the token by making a test API call
        headers = {
            'Authorization': f'Bearer {calendly_token}',
            'Content-Type': 'application/json'
        }
        
        response = requests.get('https://api.calendly.com/users/me', headers=headers, timeout=10)
        
        if response.status_code != 200:
            return JsonResponse({
                'success': False, 
                'error': 'Invalid Calendly token. Please check and try again.'
            }, status=400)
        
        # Save the credentials — to Organization (if org user) AND Admin (for legacy)
        if org:
            org.calendly_token = calendly_token
            org.calendly_scheduling_url = scheduling_url
            org.save()
        
        if admin:
            admin.calendly_token = calendly_token
            admin.calendly_scheduling_url = scheduling_url
            admin.save()
        
        return JsonResponse({
            'success': True,
            'msg': 'Calendly connected successfully!'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
@require_POST
def disconnect_calendly(request):
    """
    Disconnect Calendly integration by clearing stored credentials.
    """
    try:
        admin_id = request.session.get('admin_id')
        org_id = request.session.get('organization_id')
        admin = None
        org = None
        
        if org_id:
            from .models import Organization
            org = Organization.objects.filter(id=org_id).first()
        
        if admin_id:
            admin = Admin.objects.filter(id=admin_id).first()
        elif org and org.whatsapp_phone_id:
            admin = Admin.objects.filter(whatsapp_phone_id=org.whatsapp_phone_id).first()
        
        if not admin and not org:
            return JsonResponse({'success': False, 'error': 'Not authenticated'}, status=401)
        
        if org:
            org.calendly_token = None
            org.calendly_scheduling_url = None
            org.save()
        
        if admin:
            admin.calendly_token = None
            admin.calendly_scheduling_url = None
            admin.save()
        
        return JsonResponse({
            'success': True,
            'msg': 'Calendly disconnected successfully!'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
@require_POST
def update_followup_settings(request):
    """
    Update follow-up message settings.
    """
    try:
        admin_id = request.session.get('admin_id')
        org_id = request.session.get('organization_id')
        admin = None
        
        if admin_id:
            admin = Admin.objects.filter(id=admin_id).first()
        elif org_id:
            from .models import Organization
            org = Organization.objects.filter(id=org_id).first()
            if org and org.whatsapp_phone_id:
                admin = Admin.objects.filter(whatsapp_phone_id=org.whatsapp_phone_id).first()
        
        if not admin:
            return JsonResponse({'success': False, 'error': 'Not authenticated'}, status=401)
        
        data = json.loads(request.body)
        
        # Update follow-up enabled
        if 'followup_enabled' in data:
            admin.followup_enabled = bool(data['followup_enabled'])
        
        # Update follow-up delay (in minutes)
        if 'followup_delay_minutes' in data:
            delay = int(data['followup_delay_minutes'])
            if delay < 1 or delay > 1440:  # 1 minute to 24 hours
                return JsonResponse({
                    'success': False, 
                    'error': 'Delay must be between 1 and 1440 minutes'
                }, status=400)
            admin.followup_delay_minutes = delay
        
        admin.save()
        
        return JsonResponse({
            'success': True,
            'msg': 'Follow-up settings updated!',
            'followup_enabled': admin.followup_enabled,
            'followup_delay_minutes': admin.followup_delay_minutes
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
