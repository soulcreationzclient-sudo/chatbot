from celery import shared_task
from django.utils import timezone
from django.db import transaction
from newapp.models import User, Message, Admin, FollowUpMessage, ScheduledFollowUp
import requests
import logging
from newapp.logging_config import get_logger, log_followup_event

# Use structured logger
logger = get_logger('tasks')

# Default follow-up message templates (used if no custom messages configured)
DEFAULT_FOLLOWUP_MESSAGES = {
    1: "Hi {username}, just checking if you need any further assistance. We are here to help!",
    2: "Hi {username}, we noticed you haven't replied yet. Is there anything we can help you with?",
    3: "Hi {username}, this is our final follow-up. Feel free to reach out anytime if you need assistance. We're always here to help!"
}

MAX_FOLLOWUP_ATTEMPTS = 4  # Max steps
MAX_SEND_RETRIES = 3  # Max retry attempts per message


@shared_task
def schedule_followup(user_id, step=1):
    """
    Schedule a follow-up by creating a ScheduledFollowUp record.
    The periodic task (process_pending_followups) will pick it up when due.
    
    This replaces the old apply_async(countdown=...) approach for reliability.
    """
    try:
        user = User.objects.get(id=user_id)
        admin = user.admin_id
        organization = user.organization
        
        # Fallback: If user has organization but no admin, find matching admin
        if not admin and organization and organization.whatsapp_phone_id:
            admin = Admin.objects.filter(whatsapp_phone_id=organization.whatsapp_phone_id).first()
        
        # Check if follow-ups are enabled (organization takes priority)
        followup_enabled = True
        if organization:
            followup_enabled = getattr(organization, 'followup_enabled', True)
        elif admin:
            followup_enabled = getattr(admin, 'followup_enabled', True)
        
        if not followup_enabled:
            logger.info(f"Follow-ups disabled for org/admin. Skipping for {user.phone_no}.")
            return
        
        # Check if bot is disabled for this user
        if not getattr(user, 'bot_enabled', True):
            logger.info(f"Bot disabled for user {user.phone_no}. Skipping follow-up.")
            return
        
        # Get configured follow-up messages
        followup_configs = None
        if admin:
            followup_configs = FollowUpMessage.objects.filter(admin=admin, is_active=True).order_by('step')
        elif organization:
            # Fallback: find admin via org's whatsapp_phone_id
            if organization and organization.whatsapp_phone_id:
                matched_admin = Admin.objects.filter(whatsapp_phone_id=organization.whatsapp_phone_id).first()
                if matched_admin:
                    followup_configs = FollowUpMessage.objects.filter(admin=matched_admin, is_active=True).order_by('step')
        
        max_steps = followup_configs.count() if followup_configs and followup_configs.exists() else 3
        
        if step > max_steps:
            logger.info(f"Max follow-ups ({max_steps}) reached for {user.phone_no}. Stopping.")
            return
        
        # Get message and delay for this step
        followup_config = followup_configs.filter(step=step).first() if followup_configs else None
        
        if followup_config:
            message = followup_config.message
            delay_minutes = followup_config.delay_minutes
        else:
            message = DEFAULT_FOLLOWUP_MESSAGES.get(step, DEFAULT_FOLLOWUP_MESSAGES[3])
            # Delay priority: Organization -> Admin -> Default(10)
            if organization:
                delay_minutes = getattr(organization, 'followup_delay_minutes', 10)
            elif admin:
                delay_minutes = getattr(admin, 'followup_delay_minutes', 10)
            else:
                delay_minutes = 10
        
        # Replace placeholders
        message = message.replace("{username}", user.name or "there")
        message = message.replace("{{username}}", user.name or "there")
        message = message.replace("{name}", user.name or "there")
        message = message.replace("{{name}}", user.name or "there")
        
        # Calculate when to send
        scheduled_for = timezone.now() + timezone.timedelta(minutes=delay_minutes)
        
        # Cancel any existing pending follow-ups for this user (prevent duplicates)
        ScheduledFollowUp.objects.filter(
            user=user,
            status='pending'
        ).update(status='cancelled')
        
        # Create new scheduled follow-up
        ScheduledFollowUp.objects.create(
            user=user,
            admin=admin,
            organization=organization,
            step=step,
            scheduled_for=scheduled_for,
            status='pending',
            message=message
        )
        
        logger.info(f"📅 Follow-up step {step} scheduled for {user.phone_no} at {scheduled_for}")
        
    except User.DoesNotExist:
        logger.error(f"User with id {user_id} not found")
    except Exception as e:
        logger.error(f"Error scheduling followup: {e}", exc_info=True)


@shared_task
def process_pending_followups():
    """
    Periodic task: Process all due follow-ups.
    Run this eveny 60 seconds via Celery Beat.
    
    Uses manual 'processing' status update as a lock mechanism 
    since SQLite's select_for_update is unreliable/unsupported.
    """
    now = timezone.now()
    processed = 0
    
    # 1. Find candidates (don't lock yet)
    # Get IDs of pending follow-ups that are due
    candidate_ids = list(ScheduledFollowUp.objects.filter(
        status='pending',
        scheduled_for__lte=now
    ).values_list('id', flat=True)[:50])  # Process max 50 at a time
    
    for followup_id in candidate_ids:
        # 2. Try to acquire lock by atomic update
        # This returns the number of rows updated (0 if someone else took it or status changed)
        # This acts as a manual mutex for SQLite
        with transaction.atomic():
            updated_count = ScheduledFollowUp.objects.filter(
                id=followup_id, 
                status='pending'
            ).update(status='processing', last_attempt_at=now)
        
        if updated_count == 0:
            # Already grabbed by another worker or cancelled
            continue
            
        # 3. Process the locked item
        try:
            followup = ScheduledFollowUp.objects.get(id=followup_id)
            user = followup.user
            admin = followup.admin
            organization = followup.organization
            
            # Check if user replied since scheduling (cancel if so)
            last_user_msg = Message.objects.filter(
                user_id=user,
                who__in=['human', 'user'],  # BUG FIX: check both 'human' and 'user'
                created_at__gt=followup.created_at
            ).exists()
            
            if last_user_msg:
                followup.status = 'cancelled'
                followup.save()
                # Reset follow-up count since user replied
                user.followup_count = 0
                user.save(update_fields=['followup_count'])
                logger.info(f"⏭️ User {user.phone_no} replied. Cancelled follow-up.")
                continue
            
            # Check if bot/follow-ups enabled
            if not getattr(user, 'bot_enabled', True):
                followup.status = 'cancelled'
                followup.save()
                logger.info(f"🛑 Bot disabled for {user.phone_no}. Cancelled follow-up.")
                continue
            
            followup_enabled = True
            if organization:
                followup_enabled = getattr(organization, 'followup_enabled', True)
            elif admin:
                followup_enabled = getattr(admin, 'followup_enabled', True)
            
            if not followup_enabled:
                followup.status = 'cancelled'
                followup.save()
                logger.info(f"🛑 Follow-ups disabled for org/admin. Cancelled for {user.phone_no}.")
                continue
            
            # Get WhatsApp credentials
            whatsapp_phone_id = None
            whatsapp_token = None
            
            if organization and organization.whatsapp_phone_id and organization.whatsapp_token:
                whatsapp_phone_id = organization.whatsapp_phone_id
                whatsapp_token = organization.whatsapp_token
            elif admin and admin.whatsapp_phone_id and admin.whatsapp_token:
                whatsapp_phone_id = admin.whatsapp_phone_id
                whatsapp_token = admin.whatsapp_token
            
            # Send the message — Feature 2: Check for template message
            followup_config = None
            if admin:
                from newapp.models import FollowUpMessage as FollowUpMessageModel
                followup_config = FollowUpMessageModel.objects.filter(
                    admin=admin, step=followup.step, is_active=True
                ).first()
            
            if followup_config and followup_config.use_template and followup_config.template:
                # Send template message instead of plain text
                try:
                    from newapp.template_message_sender import send_template_message
                    
                    # Build template variables, replacing placeholders with user data
                    variables = dict(followup_config.template_variables) if followup_config.template_variables else {}
                    if user.name:
                        for key, val in variables.items():
                            if isinstance(val, str):
                                variables[key] = val.replace('{username}', user.name).replace('{{username}}', user.name).replace('{name}', user.name).replace('{{name}}', user.name)
                        # Auto-set first body param to user name if not explicitly set
                        if '1' not in variables:
                            variables['1'] = user.name
                    
                    result = send_template_message(
                        phone_number=user.phone_no,
                        template=followup_config.template,
                        variables=variables,
                        phone_id=whatsapp_phone_id,
                        token=whatsapp_token
                    )
                    success = result.get('success', False)
                    error = result.get('error') if not success else None
                    
                    if success:
                        # Store the template name in the message for tracking
                        followup.message = f"[Template: {followup_config.template.name}]"
                        followup.save(update_fields=['message'])
                except Exception as tmpl_err:
                    logger.error(f"Template send failed, falling back to text: {tmpl_err}")
                    # Fall back to plain text
                    success, error = send_whatsapp_text(
                        phone_id=whatsapp_phone_id,
                        token=whatsapp_token,
                        to_phone=user.phone_no,
                        message=followup.message
                    )
            else:
                # Standard plain text send
                success, error = send_whatsapp_text(
                    phone_id=whatsapp_phone_id,
                    token=whatsapp_token,
                    to_phone=user.phone_no,
                    message=followup.message
                )
            
            followup.attempts += 1
            
            if success:
                followup.status = 'sent'
                followup.sent_at = now
                followup.save()
                
                # Save to Message table
                Message.objects.create(
                    user_id=user,
                    messages=followup.message,
                    created_at=now,
                    who='bot'
                )
                
                # Update follow-up count
                user.followup_count = followup.step
                user.save(update_fields=['followup_count'])
                
                logger.info(f"✅ Follow-up step {followup.step} sent to {user.phone_no}")
                
                # BUG FIX: Only stop if user sent a NEW message AFTER this follow-up was scheduled
                # (not the original message that triggered the bot reply)
                user_replied_recently = Message.objects.filter(
                    user_id=user,
                    who__in=['human', 'user'],  # BUG FIX: check both 'human' and 'user'
                    created_at__gt=followup.created_at
                ).exists()

                existing_pending = ScheduledFollowUp.objects.filter(
                    user=user,
                    status='pending'
                ).exists()

                if user_replied_recently:
                    logger.info(f"⏭️ User replied recently - not scheduling next follow-up")
                    user.followup_count = 0
                    user.save(update_fields=['followup_count'])
                elif existing_pending:
                    logger.info(f"⏭️ Pending follow-up already exists - skipping duplicate")
                else:
                    # Check for "one last time" loop
                    recent_bot_message = Message.objects.filter(
                        user_id=user,
                        who='bot',
                        messages__icontains='one last time',
                        created_at__gte=now - timezone.timedelta(minutes=5)
                    ).exists()

                    if recent_bot_message:
                        logger.warning(f"⏭️ Detected one last time loop - stopping follow-ups")
                        user.followup_count = 999
                        user.save(update_fields=['followup_count'])
                    else:
                        next_step = followup.step + 1
                        schedule_followup.delay(user.id, next_step)

                processed += 1
            else:
                followup.error_message = error or 'Unknown error'
                
                if followup.attempts >= MAX_SEND_RETRIES:
                    followup.status = 'failed'
                    logger.error(f"❌ Follow-up failed after {MAX_SEND_RETRIES} attempts: {user.phone_no}")
                else:
                    # Retry logic: Reset status to pending so it gets picked up again later
                    # Push scheduled_for back 5 minutes
                    followup.status = 'pending'
                    followup.scheduled_for = now + timezone.timedelta(minutes=5)
                    logger.warning(f"⚠️ Follow-up send failed, will retry: {user.phone_no}")
                
                followup.save()
                
        except Exception as e:
            # Handle crash - try to record failure
            try:
                # Re-fetch fresh object to avoid stale data
                f = ScheduledFollowUp.objects.get(id=followup_id)
                f.attempts += 1
                f.status = 'failed' if f.attempts >= MAX_SEND_RETRIES else 'pending'
                f.error_message = str(e)
                if f.status == 'pending':
                    f.scheduled_for = now + timezone.timedelta(minutes=5)
                f.save()
                logger.error(f"❌ Error processing follow-up {followup_id}: {e}")
            except Exception as inner_e:
                logger.error(f"❌ Critical error in follow-up crash handler: {inner_e}")
    
    if processed > 0:
        logger.info(f"📬 Processed {processed} follow-ups")
    
    return processed


def send_whatsapp_text(phone_id, token, to_phone, message):
    """
    Send a text message via WhatsApp API.
    
    Returns:
        tuple: (success: bool, error: str or None)
    """
    if not phone_id or not token:
        return False, "Missing WhatsApp credentials"
    
    url = f"https://graph.facebook.com/v17.0/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": message}
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        if response.status_code == 200:
            return True, None
        else:
            error_data = response.json()
            error_msg = error_data.get('error', {}).get('message', str(error_data))
            return False, f"API error: {error_msg}"
            
    except requests.exceptions.RequestException as e:
        return False, str(e)


# Legacy function - kept for backward compatibility
# New code should use schedule_followup instead
@shared_task
def send_followup_message(user_id, step=1):
    """
    Legacy wrapper - redirects to new scheduling system.
    """
    logger.info(f"🔄 Legacy send_followup_message called. Redirecting to schedule_followup.")
    schedule_followup.delay(user_id, step)
