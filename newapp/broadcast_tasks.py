"""
Broadcast Celery Tasks - Rate-Limited Message Sending

Processes broadcast jobs in batches to comply with Meta's throughput limits.
Meta allows ~80 messages/second for standard tier accounts.
We send in batches of 50 with 1 second delays to stay well under limit.
"""

from celery import shared_task
from django.utils import timezone
from django.db import transaction
import requests
import time
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_broadcast_job(self, job_id):
    """
    Process a broadcast job - send messages in rate-limited batches.
    
    Args:
        job_id: ID of the BroadcastJob to process
    """
    from newapp.models import BroadcastJob, BroadcastMessage, Message, Admin, Organization
    
    try:
        job = BroadcastJob.objects.get(id=job_id)
    except BroadcastJob.DoesNotExist:
        logger.error(f"Broadcast job {job_id} not found")
        return
    
    # Mark job as running
    job.status = 'running'
    job.started_at = timezone.now()
    job.save(update_fields=['status', 'started_at'])
    
    # Get WhatsApp credentials
    whatsapp_phone_id = None
    whatsapp_token = None
    
    if job.organization:
        whatsapp_phone_id = job.organization.whatsapp_phone_id
        whatsapp_token = job.organization.whatsapp_token
    elif job.admin:
        whatsapp_phone_id = job.admin.whatsapp_phone_id
        whatsapp_token = job.admin.whatsapp_token
    
    if not whatsapp_phone_id or not whatsapp_token:
        job.status = 'failed'
        job.save(update_fields=['status'])
        logger.error(f"No WhatsApp credentials for broadcast job {job_id}")
        return
    
    # Process messages in batches
    BATCH_SIZE = 50
    BATCH_DELAY = 1.0  # seconds between batches
    
    pending_messages = BroadcastMessage.objects.filter(
        broadcast_job=job,
        status='pending'
    ).select_related('user')
    
    total_pending = pending_messages.count()
    processed = 0
    
    logger.info(f"Starting broadcast job {job_id}: {total_pending} messages to send")
    
    while True:
        # Get next batch
        batch = list(pending_messages[:BATCH_SIZE])
        if not batch:
            break
        
        for broadcast_msg in batch:
            try:
                # Send template message via Meta API
                success, meta_msg_id, error = send_template_message(
                    phone_id=whatsapp_phone_id,
                    token=whatsapp_token,
                    to_phone=broadcast_msg.user.phone_no,
                    template_name=job.template.name,
                    template_language=job.template.language,
                    components=build_template_components(job.template.components, job.template_variables)
                )
                
                if success:
                    broadcast_msg.status = 'sent'
                    broadcast_msg.meta_message_id = meta_msg_id or ''
                    broadcast_msg.sent_at = timezone.now()
                    job.sent_count += 1
                    
                    # Also save to Message table for conversation history
                    Message.objects.create(
                        user_id=broadcast_msg.user,
                        messages=f"[Broadcast: {job.template.name}]",
                        created_at=timezone.now(),
                        who='bot'
                    )
                else:
                    broadcast_msg.status = 'failed'
                    broadcast_msg.error_message = error or 'Unknown error'
                    job.failed_count += 1
                
                broadcast_msg.save()
                
            except Exception as e:
                broadcast_msg.status = 'failed'
                broadcast_msg.error_message = str(e)
                broadcast_msg.save()
                job.failed_count += 1
                logger.error(f"Error sending broadcast message {broadcast_msg.id}: {e}")
        
        # Save job progress
        job.save(update_fields=['sent_count', 'failed_count'])
        processed += len(batch)
        
        logger.info(f"Broadcast {job_id}: {processed}/{total_pending} processed")
        
        # Rate limiting delay between batches
        if pending_messages.filter(status='pending').exists():
            time.sleep(BATCH_DELAY)
        
        # Refresh pending messages queryset
        pending_messages = BroadcastMessage.objects.filter(
            broadcast_job=job,
            status='pending'
        ).select_related('user')
    
    # Mark job as completed
    job.status = 'completed'
    job.completed_at = timezone.now()
    job.save(update_fields=['status', 'completed_at'])
    
    logger.info(f"Broadcast job {job_id} completed: {job.sent_count} sent, {job.failed_count} failed")


def send_template_message(phone_id, token, to_phone, template_name, template_language, components=None):
    """
    Send a WhatsApp template message via Meta API.
    
    Returns:
        tuple: (success: bool, message_id: str, error: str)
    """
    url = f"https://graph.facebook.com/v17.0/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": template_language}
        }
    }
    
    # Add components if provided (for templates with variables)
    if components:
        payload["template"]["components"] = components
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        data = response.json()
        
        if response.status_code == 200 and "messages" in data:
            message_id = data["messages"][0].get("id", "")
            return True, message_id, None
        else:
            error_msg = data.get("error", {}).get("message", str(data))
            return False, None, error_msg
            
    except requests.exceptions.RequestException as e:
        return False, None, str(e)


def build_template_components(template_components, variables):
    """
    Build components array for template with variables.
    
    Args:
        template_components: List of template components from WhatsAppTemplate
        variables: Dict of variable values like {"1": "John", "2": "Order123"}
    
    Returns:
        List of component objects for Meta API, or None if no variables
    """
    if not variables:
        return None
    
    # Build components with parameters
    result = []
    
    for component in template_components:
        comp_type = component.get('type', '').lower()
        
        if comp_type == 'body':
            # Body can have multiple parameters
            params = []
            for key, value in sorted(variables.items()):
                params.append({
                    "type": "text",
                    "text": str(value)
                })
            
            if params:
                result.append({
                    "type": "body",
                    "parameters": params
                })
        
        elif comp_type == 'header':
            # Header can have image, document, video, or text
            header_format = component.get('format', 'TEXT')
            if header_format == 'TEXT' and variables.get('header'):
                result.append({
                    "type": "header",
                    "parameters": [{
                        "type": "text",
                        "text": str(variables.get('header'))
                    }]
                })
    
    return result if result else None
