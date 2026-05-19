"""
Instagram DM Webhook Controller for SpeedBot

Handles receiving and responding to Instagram Direct Messages.
Uses the same AI pipeline as WhatsApp (GPT prompts, action tags, follow-ups).

Meta API Requirements:
- Instagram Business or Creator account connected to a Facebook Page
- App permissions: instagram_manage_messages, pages_manage_metadata
- Webhook subscription for 'messages' field on Instagram product

API Reference: https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/messaging
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
from newapp.channel_sender import send_instagram_text, send_instagram_quick_replies
from newapp.logging_config import get_logger

logger = get_logger('instagram')


class InstagramController:
    """Handles Instagram DM webhook events."""

    @staticmethod
    @csrf_exempt
    def webhook(request):
        """
        Instagram webhook endpoint.
        GET: Verify webhook subscription with Meta
        POST: Process incoming Instagram DM messages
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
                logger.info("Instagram webhook verified successfully")
                return HttpResponse(challenge, status=200)
            return HttpResponse("Token verification failed", status=403)

        if request.method == 'POST':
            try:
                try:
                    data = json.loads(request.body.decode("utf-8"))
                except json.JSONDecodeError as json_err:
                    logger.error(f"Invalid JSON in Instagram webhook: {json_err}")
                    return HttpResponse("Invalid JSON", status=400)

                logger.debug(f"[IG_WEBHOOK] Received: {json.dumps(data)[:500]}")

                # Instagram webhooks come under the 'instagram' object
                # but follow similar structure to Messenger
                entries = data.get('entry', [])
                if not entries:
                    return HttpResponse("OK", status=200)

                for entry in entries:
                    # Instagram messages come in the 'messaging' array
                    messaging_events = entry.get('messaging', [])
                    
                    for event in messaging_events:
                        sender_id = event.get('sender', {}).get('id', '')
                        recipient_id = event.get('recipient', {}).get('id', '')
                        timestamp = event.get('timestamp', '')

                        if not sender_id:
                            continue

                        # Find the organization by Instagram Page ID or Account ID
                        org = Organization.objects.filter(
                            Q(instagram_page_id=recipient_id) | 
                            Q(instagram_account_id=recipient_id),
                            is_active=True
                        ).first()

                        if not org:
                            logger.warning(f"[IG] No organization found for recipient_id={recipient_id}")
                            continue

                        # Skip if it's our own message (echo)
                        if sender_id == recipient_id:
                            continue

                        # Process message
                        message_data = event.get('message', {})
                        if not message_data:
                            # Could be a read receipt, delivery, or postback
                            _handle_instagram_postback(event, org)
                            continue

                        msg_text = message_data.get('text', '')
                        msg_id = message_data.get('mid', 'unknown')

                        # Handle quick reply payloads
                        quick_reply = message_data.get('quick_reply', {})
                        if quick_reply:
                            msg_text = quick_reply.get('payload', msg_text)

                        if not msg_text.strip():
                            # Could be an attachment (image, etc.) - log and skip for now
                            attachments = message_data.get('attachments', [])
                            if attachments:
                                logger.info(f"[IG] Received attachment from {sender_id}: {attachments[0].get('type', 'unknown')}")
                            continue

                        logger.info(f"📨 [IG_INCOMING] from={sender_id} | msg_id={msg_id} | text={msg_text[:80]}")

                        # Process the message through the shared AI pipeline
                        _process_instagram_message(
                            sender_id=sender_id,
                            msg_text=msg_text,
                            organization=org,
                        )

                return HttpResponse("OK", status=200)

            except Exception as e:
                logger.error(f"[IG] Webhook error: {e}", exc_info=True)
                return HttpResponse("OK", status=200)  # Always 200 to prevent retry storms

        return HttpResponse("Method not allowed", status=405)


def _handle_instagram_postback(event, org):
    """Handle non-message events (read receipts, postbacks, etc.)."""
    if 'read' in event:
        logger.debug(f"[IG] Read receipt from {event.get('sender', {}).get('id')}")
    elif 'postback' in event:
        # Ice Breaker or Get Started button tap
        postback = event.get('postback', {})
        payload = postback.get('payload', '')
        title = postback.get('title', '')
        sender_id = event.get('sender', {}).get('id', '')
        logger.info(f"[IG] Postback from {sender_id}: title={title} payload={payload}")
        if payload:
            _process_instagram_message(sender_id, payload, org)


def _process_instagram_message(sender_id, msg_text, organization):
    """
    Process an incoming Instagram DM through the shared AI pipeline.
    Creates/updates user, generates AI response, sends reply.
    """
    from newapp.models import Admin
    
    # Get or create user — scoped to this organization
    existing_user = User.objects.filter(
        phone_no=sender_id,
        organization=organization
    ).first()

    if not existing_user:
        # Try to get Instagram username via API (optional, best-effort)
        ig_name = _fetch_instagram_username(sender_id, organization)
        
        existing_user = User.objects.create(
            phone_no=sender_id,
            name=ig_name or f'IG User {sender_id[-4:]}',
            source='Instagram',
            created_at=timezone.now(),
            organization=organization,
            is_in_inbox=True,
            bot_enabled=True,
        )
        logger.info(f"[IG] Created new user: {existing_user.phone_no} ({existing_user.name})")
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
        channel='instagram',
    )

    # Check if bot is enabled
    if not getattr(existing_user, 'bot_enabled', True):
        logger.info(f"[IG] Bot disabled for {sender_id} — skipping auto-reply")
        return

    # Get OpenAI key and prompt
    openai_key = (organization.openai_api_key or '').strip()
    if not openai_key:
        logger.warning(f"[IG] No OpenAI key configured for org {organization.name}")
        return

    # Load system prompt — prefer one assigned to 'instagram' channel
    # First try: prompt explicitly assigned to instagram
    prompt_obj = ChatGPTPrompt.objects.filter(
        organization=organization, channels__contains=['instagram']
    ).first()
    
    # Second try: default prompt (if it's not locked to another channel)
    if not prompt_obj:
        prompt_obj = ChatGPTPrompt.objects.filter(
            organization=organization, is_default=True
        ).first()
        # If the default is locked to specific channels and instagram isn't one, skip it
        if prompt_obj and prompt_obj.channels and 'instagram' not in prompt_obj.channels:
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
        logger.error(f"[IG] OpenAI error for {sender_id}: {gpt_err}")
        bot_response = "Sorry, I'm having trouble processing your message right now. Please try again."

    # Process action tags (same as WhatsApp)
    from newapp.action_tag_processor import process_response_actions
    admin = Admin.objects.filter(
        whatsapp_phone_id=organization.whatsapp_phone_id
    ).first() if organization.whatsapp_phone_id else None

    tag_result = process_response_actions(
        bot_response, admin, sender_id, organization=organization
    )
    final_text = tag_result.get('final_text', bot_response)
    button_group = tag_result.get('button_group', None)

    # Send reply via Instagram
    page_token = organization.instagram_token
    if not page_token:
        logger.error(f"[IG] No Instagram token for org {organization.name}")
        return

    if button_group:
        # Send buttons as quick replies
        quick_replies = [
            {'title': b['title'], 'payload': b.get('payload', b['title'])}
            for b in button_group.get('buttons', [])
            if b.get('type') == 'reply'
        ]
        if quick_replies:
            send_instagram_quick_replies(sender_id, final_text, quick_replies, page_token)
        else:
            send_instagram_text(sender_id, final_text, page_token)
    else:
        send_instagram_text(sender_id, final_text, page_token)

    # Save bot response
    Message.objects.create(
        user_id=existing_user,
        messages=final_text,
        created_at=timezone.now(),
        who='bot',
        channel='instagram',
    )

    # Send any API responses as separate messages
    for api_resp in tag_result.get('api_responses', []):
        if api_resp and api_resp.strip():
            send_instagram_text(sender_id, api_resp, page_token)
            Message.objects.create(
                user_id=existing_user,
                messages=api_resp,
                created_at=timezone.now(),
                who='bot',
                channel='instagram',
            )

    logger.info(f"[IG] Replied to {sender_id}: {final_text[:80]}...")


def _fetch_instagram_username(igsid, organization):
    """
    Try to fetch Instagram username via the Graph API.
    Returns the username or None.
    """
    try:
        page_token = organization.instagram_token
        if not page_token:
            return None
        url = f"https://graph.facebook.com/v21.0/{igsid}"
        params = {
            "fields": "name,username",
            "access_token": page_token
        }
        res = requests.get(url, params=params, timeout=10)
        if res.status_code == 200:
            data = res.json()
            return data.get('name') or data.get('username')
    except Exception as e:
        logger.debug(f"[IG] Could not fetch username for {igsid}: {e}")
    return None
