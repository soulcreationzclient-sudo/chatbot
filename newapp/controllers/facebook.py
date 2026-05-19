"""
Facebook Messenger Webhook Controller for SpeedBot

Handles receiving and responding to Facebook Messenger messages.
Uses the same AI pipeline as WhatsApp (GPT prompts, action tags, follow-ups).

Meta API Requirements:
- Facebook Page with Messenger enabled
- App permissions: pages_messaging, pages_read_engagement
- Webhook subscription for 'messages' and 'messaging_postbacks' fields

API Reference: https://developers.facebook.com/docs/messenger-platform
"""

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db.models import Q
import json
import logging
import os
import requests

from newapp.models import User, Message, Organization, Tag, UserTag, ChatGPTPrompt, AIAgentConfig
from newapp.channel_sender import send_facebook_text, send_facebook_quick_replies, send_facebook_typing
from newapp.logging_config import get_logger

logger = get_logger('facebook')


class FacebookController:
    """Handles Facebook Messenger webhook events."""

    @staticmethod
    @csrf_exempt
    def webhook(request):
        """
        Facebook Messenger webhook endpoint.
        GET: Verify webhook subscription with Meta
        POST: Process incoming Messenger messages
        """
        VERIFY_TOKEN = os.environ.get('WHATSAPP_VERIFY_TOKEN')  # Reuse same verify token
        if not VERIFY_TOKEN:
            logger.error("WHATSAPP_VERIFY_TOKEN environment variable not set")
            return HttpResponse("Server misconfiguration", status=500)

        if request.method == 'GET':
            mode = request.GET.get('hub.mode')
            token = request.GET.get('hub.verify_token')
            challenge = request.GET.get('hub.challenge')
            if mode == 'subscribe' and token == VERIFY_TOKEN:
                logger.info("Facebook Messenger webhook verified successfully")
                return HttpResponse(challenge, status=200)
            return HttpResponse("Token verification failed", status=403)

        if request.method == 'POST':
            try:
                try:
                    data = json.loads(request.body.decode("utf-8"))
                except json.JSONDecodeError as json_err:
                    logger.error(f"Invalid JSON in Facebook webhook: {json_err}")
                    return HttpResponse("Invalid JSON", status=400)

                logger.debug(f"[FB_WEBHOOK] Received: {json.dumps(data)[:500]}")

                # Only process 'page' object events
                if data.get('object') != 'page':
                    return HttpResponse("OK", status=200)

                entries = data.get('entry', [])
                if not entries:
                    return HttpResponse("OK", status=200)

                for entry in entries:
                    page_id = entry.get('id', '')
                    messaging_events = entry.get('messaging', [])

                    # Find organization by Facebook Page ID
                    org = Organization.objects.filter(
                        facebook_page_id=page_id,
                        is_active=True
                    ).first()

                    if not org:
                        logger.warning(f"[FB] No organization found for page_id={page_id}")
                        continue

                    for event in messaging_events:
                        sender_id = event.get('sender', {}).get('id', '')
                        recipient_id = event.get('recipient', {}).get('id', '')

                        if not sender_id:
                            continue

                        # Skip echo messages (sent by our page)
                        if sender_id == page_id:
                            continue

                        # Check for message echo (messages sent by page)
                        if event.get('message', {}).get('is_echo'):
                            continue

                        # Handle different event types
                        if 'message' in event:
                            _handle_facebook_message(event, sender_id, org)
                        elif 'postback' in event:
                            _handle_facebook_postback(event, sender_id, org)
                        elif 'read' in event:
                            logger.debug(f"[FB] Read receipt from {sender_id}")
                        elif 'delivery' in event:
                            logger.debug(f"[FB] Delivery receipt from {sender_id}")

                return HttpResponse("OK", status=200)

            except Exception as e:
                logger.error(f"[FB] Webhook error: {e}", exc_info=True)
                return HttpResponse("OK", status=200)  # Always 200 to prevent retry storms

        return HttpResponse("Method not allowed", status=405)


def _handle_facebook_message(event, sender_id, organization):
    """Handle an incoming text message or quick reply."""
    message_data = event.get('message', {})
    msg_text = message_data.get('text', '')
    msg_id = message_data.get('mid', 'unknown')

    # Handle quick reply payloads (overrides text)
    quick_reply = message_data.get('quick_reply', {})
    if quick_reply:
        msg_text = quick_reply.get('payload', msg_text)

    if not msg_text.strip():
        # Could be an attachment
        attachments = message_data.get('attachments', [])
        if attachments:
            att_type = attachments[0].get('type', 'unknown')
            logger.info(f"[FB] Received attachment from {sender_id}: {att_type}")
            # Future: handle image/file attachments
        return

    logger.info(f"📨 [FB_INCOMING] from={sender_id} | msg_id={msg_id} | text={msg_text[:80]}")

    # Process through shared AI pipeline
    _process_facebook_message(sender_id, msg_text, organization)


def _handle_facebook_postback(event, sender_id, organization):
    """Handle a postback event (Get Started button, persistent menu, etc.)."""
    postback = event.get('postback', {})
    payload = postback.get('payload', '')
    title = postback.get('title', '')

    logger.info(f"[FB] Postback from {sender_id}: title={title} payload={payload}")

    if payload:
        _process_facebook_message(sender_id, payload, organization)


def _process_facebook_message(sender_id, msg_text, organization):
    """
    Process an incoming Facebook Messenger message through the shared AI pipeline.
    Creates/updates user, generates AI response, sends reply.
    """
    from newapp.models import Admin

    # Send typing indicator
    page_token = organization.facebook_token
    if page_token:
        send_facebook_typing(sender_id, page_token, 'typing_on')

    # Get or create user — scoped to this organization
    existing_user = User.objects.filter(
        phone_no=sender_id,
        organization=organization
    ).first()

    if not existing_user:
        # Try to get Facebook user profile
        fb_name = _fetch_facebook_profile(sender_id, organization)

        existing_user = User.objects.create(
            phone_no=sender_id,
            name=fb_name or f'FB User {sender_id[-4:]}',
            source='Facebook',
            created_at=timezone.now(),
            organization=organization,
            is_in_inbox=True,
            bot_enabled=True,
        )
        logger.info(f"[FB] Created new user: {existing_user.phone_no} ({existing_user.name})")
    else:
        existing_user.is_in_inbox = True
        existing_user.archived_at = None
        existing_user.followup_count = 0
        existing_user.save(update_fields=['is_in_inbox', 'archived_at', 'followup_count'])

    # Save incoming message
    Message.objects.create(
        user_id=existing_user,
        messages=msg_text,
        created_at=timezone.now(),
        who='human',
        channel='facebook',
    )

    # Check if bot is enabled
    if not getattr(existing_user, 'bot_enabled', True):
        logger.info(f"[FB] Bot disabled for {sender_id} — skipping auto-reply")
        return

    # Get OpenAI key
    openai_key = (organization.openai_api_key or '').strip()
    if not openai_key:
        logger.warning(f"[FB] No OpenAI key configured for org {organization.name}")
        return

    # Load system prompt — prefer one assigned to 'facebook' channel
    # First try: prompt explicitly assigned to facebook
    prompt_obj = ChatGPTPrompt.objects.filter(
        organization=organization, channels__contains=['facebook']
    ).first()
    
    # Second try: default prompt (if not locked to another channel)
    if not prompt_obj:
        prompt_obj = ChatGPTPrompt.objects.filter(
            organization=organization, is_default=True
        ).first()
        if prompt_obj and prompt_obj.channels and 'facebook' not in prompt_obj.channels:
            prompt_obj = None
    
    # Third try: latest prompt with no channel restriction
    if not prompt_obj:
        prompt_obj = ChatGPTPrompt.objects.filter(
            organization=organization, channels=[]
        ).order_by('-updated_at').first()
    
    # Last resort: any prompt
    if not prompt_obj:
        prompt_obj = ChatGPTPrompt.objects.filter(
            organization=organization
        ).order_by('-updated_at').first()

    system_prompt = (
        prompt_obj.prompt_text.strip()
        if prompt_obj and prompt_obj.prompt_text
        else "Follow the admin's instructions to assist the user helpfully."
    )

    # Build conversation history
    history = Message.objects.filter(
        user_id=existing_user
    ).order_by('-created_at')[:20]

    messages_list = [{"role": "system", "content": system_prompt}]
    for h in reversed(list(history)):
        role = "assistant" if h.who == 'bot' else "user"
        messages_list.append({"role": role, "content": h.messages})
    messages_list.append({"role": "user", "content": msg_text})

    # Call OpenAI
    try:
        from openai import OpenAI
        client = OpenAI(api_key=openai_key)

        gpt_model = getattr(organization, 'gpt_model', 'gpt-4o-mini')
        if prompt_obj and prompt_obj.gpt_model:
            gpt_model = prompt_obj.gpt_model

        response = client.chat.completions.create(
            model=gpt_model,
            messages=messages_list,
        )
        bot_response = response.choices[0].message.content
    except Exception as gpt_err:
        logger.error(f"[FB] OpenAI error for {sender_id}: {gpt_err}")
        bot_response = "Sorry, I'm having trouble processing your message right now. Please try again."

    # Process action tags
    from newapp.action_tag_processor import process_response_actions
    admin = Admin.objects.filter(
        whatsapp_phone_id=organization.whatsapp_phone_id
    ).first() if organization.whatsapp_phone_id else None

    tag_result = process_response_actions(
        bot_response, admin, sender_id, organization=organization
    )
    final_text = tag_result.get('final_text', bot_response)
    button_group = tag_result.get('button_group', None)

    if not page_token:
        logger.error(f"[FB] No Facebook token for org {organization.name}")
        return

    # Turn off typing indicator
    send_facebook_typing(sender_id, page_token, 'typing_off')

    # Send reply
    if button_group:
        quick_replies = [
            {'title': b['title'], 'payload': b.get('payload', b['title'])}
            for b in button_group.get('buttons', [])
            if b.get('type') == 'reply'
        ]
        if quick_replies:
            send_facebook_quick_replies(sender_id, final_text, quick_replies, page_token)
        else:
            send_facebook_text(sender_id, final_text, page_token)
    else:
        send_facebook_text(sender_id, final_text, page_token)

    # Save bot response
    Message.objects.create(
        user_id=existing_user,
        messages=final_text,
        created_at=timezone.now(),
        who='bot',
        channel='facebook',
    )

    # Send any API responses as separate messages
    for api_resp in tag_result.get('api_responses', []):
        if api_resp and api_resp.strip():
            send_facebook_text(sender_id, api_resp, page_token)
            Message.objects.create(
                user_id=existing_user,
                messages=api_resp,
                created_at=timezone.now(),
                who='bot',
                channel='facebook',
            )

    logger.info(f"[FB] Replied to {sender_id}: {final_text[:80]}...")


def _fetch_facebook_profile(psid, organization):
    """
    Fetch Facebook user profile name via Graph API.
    Returns the name or None.
    """
    try:
        page_token = organization.facebook_token
        if not page_token:
            return None
        url = f"https://graph.facebook.com/v21.0/{psid}"
        params = {
            "fields": "first_name,last_name,name",
            "access_token": page_token
        }
        res = requests.get(url, params=params, timeout=10)
        if res.status_code == 200:
            data = res.json()
            name = data.get('name')
            if not name:
                first = data.get('first_name', '')
                last = data.get('last_name', '')
                name = f"{first} {last}".strip()
            return name or None
    except Exception as e:
        logger.debug(f"[FB] Could not fetch profile for {psid}: {e}")
    return None
