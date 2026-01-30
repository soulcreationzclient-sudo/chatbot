from celery import shared_task
from django.utils import timezone
from newapp.models import User, Message, Admin, FollowUpMessage
import requests

# Default follow-up message templates (used if no custom messages configured)
DEFAULT_FOLLOWUP_MESSAGES = {
    1: "Hi {username}, just checking if you need any further assistance. We are here to help!",
    2: "Hi {username}, we noticed you haven't replied yet. Is there anything we can help you with?",
    3: "Hi {username}, this is our final follow-up. Feel free to reach out anytime if you need assistance. We're always here to help!"
}

MAX_FOLLOWUP_ATTEMPTS = 4  # Increased to 4 to match new FollowUpMessage limit

@shared_task
def send_followup_message(user_id, step=1):
    """
    Celery task to send multi-step follow-up messages.
    Uses FollowUpMessage model if configured, otherwise falls back to defaults.
    
    Args:
        user_id: The user ID to send follow-up to
        step: Current follow-up step (1-4)
    """
    try:
        user = User.objects.get(id=user_id)
        admin = user.admin_id
        
        # Fallback: If user has organization but no admin, use first admin
        # This matches the behavior in settings.py for org users
        if not admin and user.organization:
            admin = Admin.objects.first()
        
        # Check if follow-ups are enabled for this admin
        if admin and not getattr(admin, 'followup_enabled', True):
            print(f"🛑 Follow-ups disabled for admin. Skipping for {user.phone_no}.")
            return
        
        # Check if bot is disabled for this specific user
        if not getattr(user, 'bot_enabled', True):
            print(f"🛑 Bot disabled for user {user.phone_no}. Skipping follow-up.")
            return
        
        # Get configured follow-up messages for this admin
        followup_configs = FollowUpMessage.objects.filter(admin=admin, is_active=True).order_by('step')
        max_steps = followup_configs.count() if followup_configs.exists() else 3
        
        if step > max_steps:
            print(f"🛑 Max follow-ups ({max_steps}) reached for {user.phone_no}. Stopping.")
            return
        
        # Get the last bot message time
        last_bot_msg = Message.objects.filter(user_id=user, who='bot').order_by('-created_at').first()
        
        # Check if user has replied after last bot message
        if last_bot_msg:
            last_human_msg = Message.objects.filter(
                user_id=user, who='user', created_at__gt=last_bot_msg.created_at
            ).first()
            
            if last_human_msg:
                user.followup_count = 0
                user.save()
                print(f"⏭️ User {user.phone_no} replied. Reset follow-up count. No follow-up needed.")
                return
        
        # Get message and delay for this step
        followup_config = followup_configs.filter(step=step).first()
        
        if followup_config:
            # Use configured message
            followup_text = followup_config.message
            delay_minutes = followup_config.delay_minutes
        else:
            # Fall back to default messages
            followup_text = DEFAULT_FOLLOWUP_MESSAGES.get(step, DEFAULT_FOLLOWUP_MESSAGES[3])
            delay_minutes = getattr(admin, 'followup_delay_minutes', 10)
        
        # Replace placeholders
        followup_text = followup_text.replace("{username}", user.name or "there")
        followup_text = followup_text.replace("{{username}}", user.name or "there")
        followup_text = followup_text.replace("{name}", user.name or "there")
        followup_text = followup_text.replace("{{name}}", user.name or "there")
        
        print(f"📤 Sending follow-up step {step} to {user.phone_no}: {followup_text[:50]}...")
        
        # Get admin credentials for WhatsApp API
        if not admin or not admin.whatsapp_phone_id or not admin.whatsapp_token:
            print(f"❌ Missing WhatsApp credentials for user {user.phone_no}")
            return
        
        # Send WhatsApp message directly
        url = f"https://graph.facebook.com/v17.0/{admin.whatsapp_phone_id}/messages"
        headers = {
            "Authorization": f"Bearer {admin.whatsapp_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": user.phone_no,
            "type": "text",
            "text": {"body": followup_text}
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=20)
        
        if response.status_code == 200:
            # Save the follow-up message to database
            Message.objects.create(
                user_id=user, 
                messages=followup_text, 
                created_at=timezone.now(), 
                who='bot'
            )
            
            # Update follow-up count
            user.followup_count = step
            user.save()
            
            print(f"✅ Follow-up step {step} sent to {user.phone_no}")
            
            # Schedule next follow-up if not at max
            next_step = step + 1
            next_config = followup_configs.filter(step=next_step).first()
            
            if next_step <= max_steps:
                # Get delay for next step (use next config's delay or current)
                next_delay = next_config.delay_minutes if next_config else delay_minutes
                delay_seconds = next_delay * 60
                
                send_followup_message.apply_async(
                    args=[user_id, next_step],
                    countdown=delay_seconds
                )
                print(f"⏰ Next follow-up step {next_step} scheduled in {next_delay} min")
            else:
                print(f"🏁 Final follow-up sent to {user.phone_no}. No more follow-ups.")
        else:
            print(f"❌ Failed to send follow-up: {response.status_code} - {response.text}")
                
    except User.DoesNotExist:
        print(f"❌ User with id {user_id} not found")
    except Exception as e:
        print(f"❌ Error sending followup message: {e}")
        import traceback
        traceback.print_exc()

