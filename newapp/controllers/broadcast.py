"""
Broadcast Controller - Meta-Compliant Template-Based Broadcasting

Handles:
- Syncing WhatsApp templates from Meta API
- Creating and managing broadcast jobs
- Rate-limited message sending via Celery tasks
"""

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone
import json
import requests
import logging
import os

logger = logging.getLogger(__name__)
broadcast_logger = logging.getLogger('broadcast')

from ..models import (
    Admin, Organization, User, Tag, UserTag,
    WhatsAppTemplate, BroadcastJob, BroadcastMessage
)


class BroadcastController:
    """Controller for Meta-compliant broadcast system"""
    
    @staticmethod
    def _get_credentials(request):
        """Get WhatsApp credentials from session"""
        org_id = request.session.get('organization_id')
        admin_id = request.session.get('admin_id')
        
        whatsapp_phone_id = None
        whatsapp_token = None
        waba_id = None  # WhatsApp Business Account ID
        
        if org_id:
            org = Organization.objects.filter(id=org_id).first()
            if org:
                whatsapp_phone_id = org.whatsapp_phone_id
                whatsapp_token = org.whatsapp_token
                waba_id = getattr(org, 'waba_id', '') or ''
            return {
                'phone_id': whatsapp_phone_id,
                'token': whatsapp_token,
                'waba_id': waba_id,
                'org_id': org_id,
                'admin_id': None,
                'org': org,
                'admin': None
            }
        elif admin_id:
            admin = Admin.objects.filter(id=admin_id).first()
            if admin:
                whatsapp_phone_id = admin.whatsapp_phone_id
                whatsapp_token = admin.whatsapp_token
            return {
                'phone_id': whatsapp_phone_id,
                'token': whatsapp_token,
                'org_id': None,
                'admin_id': admin_id,
                'org': None,
                'admin': admin
            }
        return None

    @csrf_exempt
    def sync_templates(request):
        """
        Sync WhatsApp message templates from Meta API.
        Fetches all templates and stores them in WhatsAppTemplate model.
        """
        broadcast_logger.info("Starting template sync")
        if request.method != 'POST':
            return JsonResponse({'error': 'POST required'}, status=405)
        
        creds = BroadcastController._get_credentials(request)
        if not creds or not creds['token']:
            return JsonResponse({'error': 'WhatsApp not configured'}, status=403)
        
        try:
            # First check if WABA ID is already configured
            waba_id = creds.get('waba_id', '')
            
            if not waba_id:
                # Try to fetch WABA ID from Meta API by querying associated business accounts
                waba_list_url = "https://graph.facebook.com/v17.0/me/whatsapp_business_accounts"
                waba_list_response = requests.get(
                    waba_list_url,
                    headers={'Authorization': f"Bearer {creds['token']}"},
                    timeout=30
                )
                waba_list_data = waba_list_response.json()
                
                waba_entries = waba_list_data.get('data', [])
                if waba_entries:
                    waba_id = waba_entries[0].get('id')
                else:
                    return JsonResponse({
                        'error': 'WABA ID not configured. Please add your WhatsApp Business Account ID in Settings > Integration.',
                        'help': 'You can find your WABA ID in Meta Business Suite > Settings > WhatsApp accounts'
                    }, status=400)
            
            # Fetch templates from Meta
            templates_url = f"https://graph.facebook.com/v17.0/{waba_id}/message_templates"
            templates_response = requests.get(
                templates_url,
                headers={'Authorization': f"Bearer {creds['token']}"},
                params={'limit': 100},
                timeout=30
            )
            
            if templates_response.status_code != 200:
                error_data = templates_response.json()
                return JsonResponse({
                    'error': f"Meta API error: {error_data.get('error', {}).get('message', 'Unknown error')}",
                    'debug': error_data
                }, status=502)
            
            templates_data = templates_response.json()
            templates = templates_data.get('data', [])
            
            synced_count = 0
            for template in templates:
                # Update or create template record
                WhatsAppTemplate.objects.update_or_create(
                    admin_id=creds['admin_id'],
                    organization_id=creds['org_id'],
                    template_id=template.get('id', ''),
                    defaults={
                        'name': template.get('name', ''),
                        'language': template.get('language', 'en_US'),
                        'status': template.get('status', 'PENDING'),
                        'category': template.get('category', 'MARKETING'),
                        'components': template.get('components', []),
                    }
                )
                synced_count += 1
            
            broadcast_logger.info(f"Successfully synced {synced_count} templates")
            return JsonResponse({
                'success': True,
                'synced_count': synced_count,
                'message': f'Synced {synced_count} templates from Meta'
            })
            
        except requests.exceptions.RequestException as e:
            logger.error(f"[sync_templates] Network error: {str(e)}")
            return JsonResponse({'error': f'Network error: {str(e)}'}, status=500)
        except Exception as e:
            logger.error(f"[sync_templates] Error: {str(e)}")
            return JsonResponse({'error': f'Error syncing templates: {str(e)}'}, status=500)

    @csrf_exempt
    def list_templates(request):
        """List all synced templates for this org/admin"""
        creds = BroadcastController._get_credentials(request)
        if not creds:
            return JsonResponse({'error': 'Not authenticated'}, status=401)
        
        if creds['org_id']:
            templates = WhatsAppTemplate.objects.filter(organization_id=creds['org_id'])
        elif creds['admin_id']:
            templates = WhatsAppTemplate.objects.filter(admin_id=creds['admin_id'])
        else:
            templates = WhatsAppTemplate.objects.none()
        
        # Filter by status if requested
        status_filter = request.GET.get('status')
        if status_filter:
            templates = templates.filter(status=status_filter.upper())
        
        data = [{
            'id': t.id,
            'template_id': t.template_id,
            'name': t.name,
            'language': t.language,
            'status': t.status,
            'category': t.category,
            'components': t.components,
            'synced_at': t.synced_at.isoformat() if t.synced_at else None,
        } for t in templates]
        
        return JsonResponse({'templates': data})

    @csrf_exempt
    def create_broadcast(request):
        """
        Create a new broadcast job.
        Only allows APPROVED templates.
        """
        logger.info("[create_broadcast] Starting broadcast creation")
        if request.method != 'POST':
            return JsonResponse({'error': 'POST required'}, status=405)
        
        creds = BroadcastController._get_credentials(request)
        if not creds or not creds['token']:
            broadcast_logger.warning("WhatsApp not configured")
            return JsonResponse({'error': 'WhatsApp not configured'}, status=403)
        
        try:
            # Parse request data
            if request.content_type == 'application/json':
                data = json.loads(request.body)
            else:
                data = request.POST
            
            template_id = data.get('template_id')
            tag_id = data.get('tag_id')
            name = data.get('name', '')
            template_variables = data.get('variables', {})
            
            if not template_id:
                return JsonResponse({'error': 'template_id is required'}, status=400)
            
            # Get template and verify it's approved
            template = WhatsAppTemplate.objects.filter(id=template_id).first()
            if not template:
                return JsonResponse({'error': 'Template not found'}, status=404)
            
            if template.status != 'APPROVED':
                return JsonResponse({
                    'error': f'Template "{template.name}" is not approved. Status: {template.status}. Only APPROVED templates can be used for broadcasting.'
                }, status=400)
            
            # Get recipients
            if creds['org_id']:
                users = User.objects.filter(organization_id=creds['org_id'], is_in_inbox=True)
            elif creds['admin_id']:
                users = User.objects.filter(admin_id=creds['admin_id'], is_in_inbox=True)
            else:
                users = User.objects.none()
            
            # Filter by tag if specified
            tag = None
            if tag_id:
                tag = Tag.objects.filter(id=tag_id).first()
                if tag:
                    user_ids = UserTag.objects.filter(tag=tag).values_list('user_id', flat=True)
                    users = users.filter(id__in=user_ids)
            
            recipient_count = users.count()
            if recipient_count == 0:
                return JsonResponse({'error': 'No recipients found for this broadcast'}, status=400)
            
            # Create broadcast job
            job = BroadcastJob.objects.create(
                admin_id=creds['admin_id'],
                organization_id=creds['org_id'],
                template=template,
                tag=tag,
                name=name or f"Broadcast: {template.name}",
                status='pending',
                total_recipients=recipient_count,
                template_variables=template_variables if isinstance(template_variables, dict) else {}
            )
            
            # Create BroadcastMessage records for each recipient
            broadcast_messages = [
                BroadcastMessage(
                    broadcast_job=job,
                    user=user,
                    status='pending'
                )
                for user in users
            ]
            BroadcastMessage.objects.bulk_create(broadcast_messages, batch_size=500)
            
            # Trigger the Celery task to process this broadcast
            from newapp.broadcast_tasks import process_broadcast_job
            broadcast_logger.info(f"Broadcast job {job.id} created for {recipient_count} recipients")
            process_broadcast_job.delay(job.id)
            
            return JsonResponse({
                'success': True,
                'job_id': job.id,
                'total_recipients': recipient_count,
                'message': f'Broadcast created. Sending to {recipient_count} recipients.'
            })
            
        except json.JSONDecodeError:
            broadcast_logger.error("Invalid JSON in broadcast request")
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            broadcast_logger.error(f"Broadcast error: {str(e)}")
            return JsonResponse({'error': f'Error creating broadcast: {str(e)}'}, status=500)

    @csrf_exempt
    def get_broadcast_status(request, job_id):
        """Get the status of a broadcast job"""
        creds = BroadcastController._get_credentials(request)
        if not creds:
            return JsonResponse({'error': 'Not authenticated'}, status=401)
        
        job = BroadcastJob.objects.filter(id=job_id).first()
        if not job:
            return JsonResponse({'error': 'Broadcast job not found'}, status=404)
        
        # Verify ownership
        if creds['org_id'] and job.organization_id != creds['org_id']:
            return JsonResponse({'error': 'Permission denied'}, status=403)
        if creds['admin_id'] and str(job.admin_id) != str(creds['admin_id']):
            return JsonResponse({'error': 'Permission denied'}, status=403)
        
        return JsonResponse({
            'id': job.id,
            'name': job.name,
            'template_name': job.template.name,
            'status': job.status,
            'total_recipients': job.total_recipients,
            'sent_count': job.sent_count,
            'failed_count': job.failed_count,
            'pending_count': job.total_recipients - job.sent_count - job.failed_count,
            'progress_percent': round((job.sent_count + job.failed_count) / max(job.total_recipients, 1) * 100, 1),
            'created_at': job.created_at.isoformat() if job.created_at else None,
            'started_at': job.started_at.isoformat() if job.started_at else None,
            'completed_at': job.completed_at.isoformat() if job.completed_at else None,
        })

    @csrf_exempt
    def list_broadcasts(request):
        """List all broadcast jobs for this org/admin"""
        creds = BroadcastController._get_credentials(request)
        if not creds:
            return JsonResponse({'error': 'Not authenticated'}, status=401)
        
        if creds['org_id']:
            jobs = BroadcastJob.objects.filter(organization_id=creds['org_id'])
        elif creds['admin_id']:
            jobs = BroadcastJob.objects.filter(admin_id=creds['admin_id'])
        else:
            jobs = BroadcastJob.objects.none()
        
        jobs = jobs.order_by('-created_at')[:50]  # Last 50 broadcasts
        
        data = [{
            'id': j.id,
            'name': j.name,
            'template_name': j.template.name if j.template else 'Unknown',
            'status': j.status,
            'total_recipients': j.total_recipients,
            'sent_count': j.sent_count,
            'failed_count': j.failed_count,
            'created_at': j.created_at.isoformat() if j.created_at else None,
        } for j in jobs]
        
        return JsonResponse({'broadcasts': data})

    @csrf_exempt
    def broadcast_dashboard(request):
        """Render broadcast dashboard page"""
        creds = BroadcastController._get_credentials(request)
        if not creds:
            return redirect('/login/')
        
        # Get templates (only approved for selection)
        if creds['org_id']:
            templates = WhatsAppTemplate.objects.filter(organization_id=creds['org_id'], status='APPROVED')
            tags = Tag.objects.filter(organization_id=creds['org_id'])
            jobs = BroadcastJob.objects.filter(organization_id=creds['org_id']).order_by('-created_at')[:20]
        elif creds['admin_id']:
            templates = WhatsAppTemplate.objects.filter(admin_id=creds['admin_id'], status='APPROVED')
            tags = Tag.objects.filter(admin_id=creds['admin_id'])
            jobs = BroadcastJob.objects.filter(admin_id=creds['admin_id']).order_by('-created_at')[:20]
        else:
            templates = WhatsAppTemplate.objects.none()
            tags = Tag.objects.none()
            jobs = BroadcastJob.objects.none()
        
        return render(request, 'broadcast/dashboard.html', {
            'templates': templates,
            'tags': tags,
            'jobs': jobs,
        })
