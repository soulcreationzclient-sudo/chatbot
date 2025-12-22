from celery import shared_task
from django.utils import timezone
from newapp.models import User, Message, Admin
import requests

# Follow-up message templates for each attempt
FOLLOWUP_MESSAGES = {
    1: "Hi {username}, just checking if you need any further assistance. We are here to help!",
    2: "Hi {username}, we noticed you haven't replied yet. Is there anything we can help you with?",
    3: "Hi {username}, this is our final follow-up. Feel free to reach out anytime if you need assistance. We're always here to help!"
}

MAX_FOLLOWUP_ATTEMPTS = 3
FOLLOWUP_DELAY_SECONDS = 30  # 30 seconds for testing, change to 600 (10 min) for production

@shared_task
def send_followup_message(user_id, message_text=None):
    """
    Celery task to send follow-up messages with max 3 attempts.
    - 1st attempt: Initial follow-up
    - 2nd attempt: Second reminder
    - 3rd attempt: Final message (then stop)
    """
    try:
        user = User.objects.get(id=user_id)
        
        # Check current follow-up count
        current_attempt = getattr(user, 'followup_count', 0) + 1
        
        if current_attempt > MAX_FOLLOWUP_ATTEMPTS:
            print(f"🛑 Max follow-ups ({MAX_FOLLOWUP_ATTEMPTS}) reached for {user.phone_no}. Stopping.")
            return
        
        # Check if follow-ups are enabled for this admin
        admin = user.admin_id
        if admin and not getattr(admin, 'followup_enabled', True):
            print(f"🛑 Follow-ups disabled for admin. Skipping for {user.phone_no}.")
            return
        
        # Get the last bot message time
        last_bot_msg = Message.objects.filter(user_id=user, who='bot').order_by('-created_at').first()
        
        # Check if user has replied after last bot message
        last_human_msg = None
        if last_bot_msg:
            last_human_msg = Message.objects.filter(
                user_id=user, who='human', created_at__gt=last_bot_msg.created_at
            ).order_by('-created_at').first()

        # If user replied, reset follow-up counter and don't send
        if last_human_msg:
            user.followup_count = 0
            user.save()
            print(f"⏭️ User {user.phone_no} replied. Reset follow-up count. No follow-up needed.")
            return
        
        # Get message for this attempt
        followup_text = FOLLOWUP_MESSAGES.get(current_attempt, FOLLOWUP_MESSAGES[3])
        followup_text = followup_text.replace("{username}", user.name or "there")
        
        print(f"📤 Sending follow-up #{current_attempt} to {user.phone_no}: {followup_text}")
        
        # Get admin credentials for WhatsApp API
        admin = user.admin_id
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
            user.followup_count = current_attempt
            user.save()
            
            print(f"✅ Follow-up #{current_attempt} sent to {user.phone_no}")
            
            # Schedule next follow-up if not at max
            if current_attempt < MAX_FOLLOWUP_ATTEMPTS:
                # Use admin's configured delay (in minutes), convert to seconds
                delay_seconds = getattr(admin, 'followup_delay_minutes', 10) * 60
                send_followup_message.apply_async(
                    args=[user_id],
                    countdown=delay_seconds
                )
                print(f"⏰ Next follow-up #{current_attempt + 1} scheduled in {delay_seconds}s ({admin.followup_delay_minutes} min)")
            else:
                print(f"🏁 Final follow-up sent to {user.phone_no}. No more follow-ups.")
        else:
            print(f"❌ Failed to send follow-up: {response.status_code} - {response.text}")
                
    except User.DoesNotExist:
        print(f"❌ User with id {user_id} not found")
    except Exception as e:
        print(f"❌ Error sending followup message: {e}")
