from django.db.models import Q
from django.http import HttpResponse, JsonResponse
import requests  # Single import
from ..models import Admin
from django.shortcuts import redirect, render
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from datetime import datetime, timedelta
from urllib.parse import urlencode
import json
import logging
import sys

from newapp.models import (
    User, Message, Admin, Tag, UserTag, 
    ChatGPTPrompt, AIAgentConfig, Organization
)
from newapp.views import send_whatsapp_reply
from newapp.tasks import send_followup_message, schedule_followup
from newapp.logging_config import get_logger, log_message_received, log_message_sent, log_error
import os

# Import third-party libraries
from pinecone import Pinecone
from pinecone_plugins.assistant.models.chat import Message as Pinemessage
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

# Initialize structured logger for webhook
webhook_logger = get_logger('webhook')


def get_credentials(admin_check, org_check):
    """Get WhatsApp/OpenAI credentials - prefer organization, fallback to admin"""
    if org_check:
        return {
            'whatsapp_phone_id': org_check.whatsapp_phone_id or '',
            'whatsapp_token': org_check.whatsapp_token or '',
            'openai_key': (org_check.openai_api_key or '').strip(),
            'pinecone_token': (org_check.pinecone_token or '').strip(),
            'chatgpt_mode': getattr(org_check, 'chatgpt_mode', 'prompt'),
            'gpt_model': getattr(org_check, 'gpt_model', 'gpt-4o-mini'),
            'calendly_url': getattr(org_check, 'calendly_scheduling_url', ''),
            'source': 'organization',
            'source_id': org_check.id,
        }
    elif admin_check:
        return {
            'whatsapp_phone_id': admin_check.whatsapp_phone_id or '',
            'whatsapp_token': admin_check.whatsapp_token or '',
            'openai_key': (getattr(admin_check, 'openai_api_key', '') or '').strip(),
            'pinecone_token': (getattr(admin_check, 'pinecone_token', '') or '').strip(),
            'chatgpt_mode': getattr(admin_check, 'chatgpt_mode', 'prompt'),
            'gpt_model': 'gpt-4o-mini',
            'calendly_url': getattr(admin_check, 'calendly_scheduling_url', ''),
            'source': 'admin',
            'source_id': admin_check.id,
        }
    return {
        'whatsapp_phone_id': '',
        'whatsapp_token': '',
        'openai_key': '',
        'pinecone_token': '',
        'chatgpt_mode': 'prompt',
        'gpt_model': 'gpt-4o-mini',
        'calendly_url': '',
        'source': None,
        'source_id': None,
    }



class whatsappcontroller:
    @csrf_exempt
    def connect(request):
        phone_id = request.POST.get('phone_id') or ''
        user_token = request.POST.get('user_token') or ''
        waba_id = request.POST.get('waba_id') or ''  # Optional WABA ID for template sync

        headers = {
            'Authorization': f"Bearer {user_token}"
        }
        url = f"https://graph.facebook.com/v21.0/{phone_id}"

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status() 

            if (response.status_code == 200):
                response_data = response.json()
                display_phone_no = str(
                    response_data.get('display_phone_number', ''))
                
                org_id = request.session.get('organization_id')
                admin_id = request.session.get('admin_id')
                
                if org_id:
                    # Organization-based auth
                    from newapp.models import Organization
                    update_fields = {
                        'whatsapp_phone_id': phone_id,
                        'whatsapp_token': user_token,
                        'display_phone_no': display_phone_no
                    }
                    if waba_id:
                        update_fields['waba_id'] = waba_id
                    Organization.objects.filter(id=org_id).update(**update_fields)
                    messages.success(request, "WhatsApp connected successfully!")
                    return redirect(request.META.get('HTTP_REFERER', '/'))
                elif admin_id:
                    # Legacy admin-based auth
                    Admin.objects.filter(id=admin_id).update(
                        whatsapp_phone_id=phone_id,
                        whatsapp_token=user_token,
                        display_phone_no=display_phone_no
                    )
                    messages.success(request, "WhatsApp connected successfully!")
                    return redirect(request.META.get('HTTP_REFERER', '/'))
                    
                messages.error(request, "Not authenticated")
                return redirect(request.META.get('HTTP_REFERER', '/'))
           
        except requests.exceptions.RequestException as e:
            messages.warning(request, "WhatsApp error - please try again later")
            return redirect(request.META.get('HTTP_REFERER', '/'))

        messages.warning(request, "Server error")
        return redirect(request.META.get('HTTP_REFERER', '/'))

    @csrf_exempt
    def send_whatsapp_message(request):
        if request.method != 'POST':
            return JsonResponse({"error": "Method not allowed"}, status=405)

        phone_number_id = (request.POST.get('phone_number_id') or '').strip()
        phone = (request.POST.get('phone') or '').strip()
        message = (request.POST.get('message') or '').strip()

        if not phone:
            return JsonResponse({"error": "Phone number missing"}, status=400)

        # Check both Admin and Organization tables for WhatsApp token
        token = Admin.objects.filter(whatsapp_phone_id=phone_number_id)\
                            .values_list('whatsapp_token', flat=True).first()
        if not token:
            from ..models import Organization
            token = Organization.objects.filter(whatsapp_phone_id=phone_number_id)\
                                .values_list('whatsapp_token', flat=True).first()
        if not token:
            return JsonResponse({"error": "WhatsApp token missing"}, status=400)

        url = f"https://graph.facebook.com/v17.0/{phone_number_id}/messages"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        payload = {
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "text",
            "text": {"body": message}
        }

        try:
            res = requests.post(url, json=payload, headers=headers, timeout=20)
            try:
                data = res.json()
            except Exception:
                data = {"raw_text": res.text}

            if res.status_code == 200 and "messages" in data:
                # persist bot message (uses timezone.now)
                user = User.objects.filter(phone_no=phone).first()
                if not user:
                    user = User.objects.create(name='bot', phone_no=phone, created_at=timezone.now(), is_in_inbox=True)
                Message.objects.create(user_id=user, messages=message, created_at=timezone.now(), who='bot')
                return JsonResponse({"ok": True, "provider_response": data}, status=200)
            else:
                err = (data.get("error") or {}).get("message") or data
                return JsonResponse({"ok": False, "provider_response": err}, status=502)

        except Exception as e:
            return JsonResponse({"ok": False, "exception": str(e)}, status=500)

    
    # @csrf_exempt
    # def send_whatsapp_message(request):
    #     if request.method == 'GET':
    #         # Render the send message form on GET requests
    #         return render(request, 'send_message.html')

    #     elif request.method == 'POST':
    #         phone_number_id = request.POST.get('phone_number_id', '')
    #         phone = request.POST.get('phone', '')
    #         message = request.POST.get('message', '')

    #         if phone == '':
    #             return HttpResponse("Phone number missing", status=400)

    #         token = Admin.objects.filter(whatsapp_phone_id=phone_number_id).values_list('whatsapp_token', flat=True).first()
    #         if token is None or token == '':
    #             return HttpResponse("WhatsApp token missing", status=400)

    #         response_data = None
    #         success_message = None
    #         error_message = None

    #         url = f"https://graph.facebook.com/v17.0/{phone_number_id}/messages"
    #         headers = {
    #             "Authorization": f"Bearer {token}",
    #             "Content-Type": "application/json"
    #         }
    #         payload = {
    #             "messaging_product": "whatsapp",
    #             "to": phone,
    #             "type": "text",
    #             "text": {"body": message}
    #         }

    #         try:
    #             res = requests.post(url, json=payload, headers=headers)
    #             response_data = res.json()

    #             if res.status_code == 200 and "messages" in response_data:
    #                 success_message = "✅ Message sent successfully!"
    #                 existing_user = User.objects.filter(phone_no=phone).first()
    #                 if not existing_user:
    #                     new_user = User.objects.create(
    #                         name='bot',
    #                         phone_no=phone,
    #                         created_at=datetime.now()
    #                     )
    #                     user_id = new_user.id
    #                 else:
    #                     user_id = existing_user.id

    #                 user_instance = User.objects.get(id=user_id)
    #                 Message.objects.create(
    #                     user_id=user_instance,
    #                     messages=message,
    #                     created_at=datetime.now(),
    #                     who='bot'
    #                 )
    #             else:
    #                 error_detail = response_data.get("error", {}).get("message", "Unknown error")
    #                 error_message = f"❌ Failed to send message: {error_detail}"

    #         except Exception as e:
    #             error_message = f"❌ Exception occurred: {str(e)}"

    #         return render(request, 'send_message.html', {
    #             'response': response_data,
    #             'success_message': success_message,
    #             'error_message': error_message,
    #             'phone_number_id': phone_number_id,
    #             'phone': phone,
    #             'message': message
    #         })

    #     else:
    #         return HttpResponse("Method not allowed", status=405)

    @csrf_exempt
    def get_message(request):
        # SECURITY: Use environment variable for webhook verification
        # SECURITY: Require environment variable for webhook verification
        VERIFY_TOKEN = os.environ.get('WHATSAPP_VERIFY_TOKEN')
        if not VERIFY_TOKEN:
            webhook_logger.error("WHATSAPP_VERIFY_TOKEN environment variable not set")
            return HttpResponse("Server misconfiguration", status=500)

        if request.method == 'GET':
            mode = request.GET.get('hub.mode')
            token = request.GET.get('hub.verify_token')
            challenge = request.GET.get('hub.challenge')
            if mode == 'subscribe' and token == VERIFY_TOKEN:
                return HttpResponse(challenge, status=200)
            return HttpResponse("Token verification failed", status=403)

        if request.method == 'POST':
            try:
                # BUG FIX: Handle malformed JSON gracefully
                try:
                    data = json.loads(request.body.decode("utf-8"))
                except json.JSONDecodeError as json_err:
                    webhook_logger.error(f"Invalid JSON in webhook: {json_err}")
                    return HttpResponse("Invalid JSON", status=400)
                webhook_logger.debug(f"[RAW_WEBHOOK] Received data: {json.dumps(data)[:500]}")
                webhook_logger.debug(f"Received webhook data: {data}")
                sys.stdout.flush()

                entries = data.get('entry') or []
                if not entries:
                    webhook_logger.debug("[RAW_WEBHOOK] No entries in webhook data - acknowledging silently")
                    return HttpResponse("OK", status=200)  # acknowledge silently

                for entry in entries:
                    changes = entry.get('changes') or []
                    for change in changes:
                        value = change.get('value') or {}
                        metadata = value.get("metadata") or {}
                        phone_number_id = metadata.get('phone_number_id')

                        # Check both Admin and Organization for this phone_number_id
                        admin_check = Admin.objects.filter(whatsapp_phone_id=phone_number_id).first()
                        org_check = None
                        
                        # Also check Organization
                        from newapp.models import Organization
                        org_check = Organization.objects.filter(whatsapp_phone_id=phone_number_id).first()
                        
                        if not admin_check and not org_check:
                            continue
                        
                        # Get credentials from organization (preferred) or admin
                        creds = get_credentials(admin_check, org_check)

                        for m in value.get('messages') or []:
                            msg_text = None # Reset for each message iteration
                            msg_type = m.get('type')
                            phone = m.get('from')
                            msg_id = m.get('id', 'unknown')
                            timestamp = m.get('timestamp', 'unknown')
                            
                            # LOG INCOMING MESSAGE
                            log_message_received(
                                phone=phone,
                                msg_type=msg_type,
                                content=(m.get('text') or {}).get('body', f'[{msg_type}]'),
                                source=f"phone_id={phone_number_id}"
                            )
                            webhook_logger.info(f"📨 [INCOMING] msg_id={msg_id} | from={phone} | type={msg_type} | timestamp={timestamp} | creds_source={creds['source']}")
                            
                            # Get user info from contacts
                            contacts = value.get('contacts', [])
                            wa_name = None
                            if contacts and len(contacts) > 0:
                                wa_name = contacts[0].get('profile', {}).get('name')

                            # Get or create user — ORG-SCOPED to prevent cross-org leakage
                            existing_user = None
                            if org_check:
                                existing_user = User.objects.filter(phone_no=phone, organization=org_check).first()
                            elif admin_check:
                                existing_user = User.objects.filter(phone_no=phone, admin_id=admin_check).first()

                            if not existing_user:
                                # No user in this org — create a new one (even if phone exists in another org)
                                existing_user = User(
                                    phone_no=phone,
                                    created_at=timezone.now(),
                                    admin_id=admin_check,
                                    is_in_inbox=True,
                                )
                                if org_check:
                                    existing_user.organization = org_check
                            else:
                                # Ensure user is visible in inbox when they message
                                existing_user.is_in_inbox = True
                                existing_user.archived_at = None  # Clear archive flag
                                    
                            if wa_name:
                                existing_user.name = wa_name
                            
                            # BUG FIX: Always save user state (is_in_inbox, name, etc.)
                            # Reset follow-up counter for actual human messages
                            human_message_types = ['text', 'image', 'document', 'audio']
                            if msg_type in human_message_types:
                                existing_user.followup_count = 0
                            existing_user.save()
                            webhook_logger.info(f"User {phone} saved: inbox={existing_user.is_in_inbox} bot={existing_user.bot_enabled}")

                            
                            # ==================== IMAGE/DOCUMENT HANDLING ====================
                            media_already_saved = False  # Track if we already saved the human message
                            if msg_type == 'image':
                                from newapp.image_pdf_service import analyze_media_message, save_chat_media
                                
                                image_info = m.get('image', {})
                                media_id = image_info.get('id')
                                caption = image_info.get('caption', 'What can you see in this image? Describe it in detail.')
                                
                                # Save media locally
                                local_url = save_chat_media(media_id, creds['whatsapp_token'])
                                msg_content = f"[Image] {caption}"
                                if local_url:
                                    msg_content = f"[Image: {local_url}] {caption}"
                                
                                # Save incoming message
                                Message.objects.create(
                                    user_id=existing_user,
                                    messages=msg_content,
                                    created_at=timezone.now(),
                                    who='human'
                                )
                                media_already_saved = True
                                
                                # Analyze the image
                                webhook_logger.info(f"Analyzing image for {phone}")
                                reply = analyze_media_message(
                                    media_id=media_id,
                                    media_type='image',
                                    user_question=caption,
                                    admin=admin_check,
                                    openai_key=creds.get('openai_key'),
                                    whatsapp_token=creds.get('whatsapp_token')
                                )
                                webhook_logger.debug(f"Vision analysis complete: {reply[:100]}...")
                                
                                # Store context for follow-up questions
                                from newapp.image_pdf_service import store_document_context
                                store_document_context(phone, reply, 'image')
                                
                                # Inject analysis into message text for AI to process in-character
                                # The raw analysis is stored in document context (loaded at line 632)
                                # Keep msg_text SHORT so it doesn't clutter inbox or AI responses
                                msg_text = f"[User sent an image] {caption}"
                            
                            elif msg_type == 'document':
                                from newapp.image_pdf_service import analyze_media_message, save_chat_media
                                
                                doc_info = m.get('document', {})
                                media_id = doc_info.get('id')
                                mime_type = doc_info.get('mime_type', '')
                                filename = doc_info.get('filename', 'document')
                                caption = doc_info.get('caption', 'Please analyze this document and tell me what it contains.')
                                
                                # Save media locally
                                local_url = save_chat_media(media_id, creds['whatsapp_token'])
                                msg_content = f"[Document: {filename}] {caption}"
                                if local_url:
                                    msg_content = f"[Document: {local_url}] {caption}"
                                
                                # Save incoming message
                                Message.objects.create(
                                    user_id=existing_user,
                                    messages=msg_content,
                                    created_at=timezone.now(),
                                    who='human'
                                )
                                media_already_saved = True
                                
                                # Analyze the document
                                webhook_logger.info(f"Analyzing document {filename} for {phone}")
                                reply = analyze_media_message(
                                    media_id=media_id,
                                    media_type='document',
                                    user_question=caption,
                                    admin=admin_check,
                                    mime_type=mime_type,
                                    openai_key=creds.get('openai_key'),
                                    whatsapp_token=creds.get('whatsapp_token')
                                )
                                webhook_logger.debug(f"Vision analysis complete: {reply[:100]}...")
                                
                                # Store context for follow-up questions
                                from newapp.image_pdf_service import store_document_context
                                store_document_context(phone, reply, 'document', filename)
                                
                                # Inject analysis into message text for AI to process in-character
                                # The raw analysis is stored in document context (loaded at line 632)
                                # Keep msg_text SHORT so it doesn't clutter inbox or AI responses  
                                msg_text = f"[User sent a document: {filename}] {caption}"
                                
                                # Need to skip the 'msg_text' retrieval block below since we just set it

                            
                            elif msg_type == 'audio':
                                # ==================== AUDIO/VOICE HANDLING ====================
                                from newapp.image_pdf_service import transcribe_audio
                                
                                audio_info = m.get('audio', {})
                                media_id = audio_info.get('id')
                                
                                if not media_id:
                                    webhook_logger.warning(f"Audio message from {phone} has no media ID")
                                    continue
                                
                                # Save incoming voice message record
                                Message.objects.create(
                                    user_id=existing_user,
                                    messages="[Voice Message]",
                                    created_at=timezone.now(),
                                    who='human'
                                )
                                media_already_saved = True
                                
                                # Transcribe audio using OpenAI Whisper
                                webhook_logger.info(f"Transcribing audio for {phone}")
                                transcription = transcribe_audio(
                                    media_id=media_id,
                                    openai_key=creds.get('openai_key'),
                                    whatsapp_token=creds.get('whatsapp_token')
                                )
                                
                                if transcription:
                                    webhook_logger.info(f"Audio transcribed for {phone}: {transcription[:80]}...")
                                    msg_text = transcription  # Feed transcription to AI as if user typed it
                                    
                                    # BUG FIX: Update the saved [Voice Message] with actual transcription
                                    # so conversation history has meaningful content for future AI calls
                                    try:
                                        last_voice_msg = Message.objects.filter(
                                            user_id=existing_user,
                                            messages="[Voice Message]",
                                            who='human'
                                        ).order_by('-id').first()
                                        if last_voice_msg:
                                            last_voice_msg.messages = f"[Voice Message] {transcription}"
                                            last_voice_msg.save(update_fields=['messages'])
                                            webhook_logger.debug(f"Updated voice message record with transcription for {phone}")
                                    except Exception as vm_err:
                                        webhook_logger.error(f"Failed to update voice message record: {vm_err}")
                                else:
                                    webhook_logger.warning(f"Failed to transcribe audio for {phone}")
                                    # Send error message to user
                                    error_msg = "Sorry, I couldn't understand that audio. Could you type your message instead?"
                                    Message.objects.create(
                                        user_id=existing_user,
                                        messages=error_msg,
                                        created_at=timezone.now(),
                                        who='bot'
                                    )
                                    whatsapp_api_url = f"https://graph.facebook.com/v17.0/{phone_number_id}/messages"
                                    headers = {
                                        "Authorization": f"Bearer {creds['whatsapp_token']}",
                                        "Content-Type": "application/json"
                                    }
                                    payload = {
                                        "messaging_product": "whatsapp",
                                        "to": phone,
                                        "type": "text",
                                        "text": {"body": error_msg}
                                    }
                                    requests.post(whatsapp_api_url, json=payload, headers=headers)
                                    continue
                                # ==================== END AUDIO HANDLING ====================
                            
                            elif msg_type != 'text':
                                # Skip other message types (video, sticker, location, etc.)
                                continue
                            # ==================== END IMAGE/DOCUMENT/AUDIO HANDLING ====================

                            # Only get text if not already set by Vision
                            if msg_text is None:
                                msg_text = (m.get('text') or {}).get('body') or ""
                            if not msg_text.strip():
                                continue

                            # BUG FIX: Improved deduplication with better logging
                            # Only check for exact duplicates within 30 seconds
                            last_msg = Message.objects.filter(
                                who='human', 
                                user_id=existing_user
                            ).order_by('-id').first()
                            
                            if last_msg and last_msg.messages and msg_text:
                                if last_msg.messages.strip() == msg_text.strip():
                                    time_diff = (timezone.now() - last_msg.created_at).total_seconds()
                                    if time_diff < 30:
                                        webhook_logger.info(f"Skipping duplicate message from {phone}: {msg_text[:30]}...")
                                        continue

                            # Only save text message if not already saved by image/doc handler
                            if not media_already_saved:
                                Message.objects.create(
                                    user_id=existing_user,
                                    messages=msg_text,
                                    created_at=timezone.now(),
                                    who='human'
                                )

                            # ==================== BOT TOGGLE CHECK ====================
                            # If bot is disabled for this user, skip AI response
                            if not getattr(existing_user, 'bot_enabled', True):
                                webhook_logger.info(f"Bot disabled for {phone} - skipping auto-reply")
                                continue
                            # ==================== END BOT TOGGLE CHECK ====================

                            # ==================== AUTOMATED MESSAGE DETECTION ====================
                            # BUG FIX: Detect if the incoming message is from another bot/automated system
                            # Check for common automated message patterns to prevent bot-on-bot conversations
                            automated_patterns = [
                                'demo account',
                                'follow up',
                                'one last time',
                                'check if you need',
                            ]

                            is_automated = any(pattern in msg_text.lower() for pattern in automated_patterns) if msg_text else False

                            if is_automated:
                                webhook_logger.info(f"🤖 Detected automated message from {phone}, skipping AI response")
                                # Don't generate AI response for automated messages - just log and continue
                                continue
                            # ==================== END AUTOMATED MESSAGE DETECTION ====================

                            # ==================== KEYWORD MACRO TAGGING ====================
                            # Check if user input matches any tag keywords (Manual Rule Mode)
                            try:
                                msg_lower = msg_text.lower().strip()
                                # Get all tags with keywords for this admin/org
                                keyword_tags = Tag.objects.filter(
                                    Q(admin=admin_check) | Q(organization=org_check) if org_check else Q(admin=admin_check),
                                    auto_apply=True,
                                    keyword__isnull=False
                                ).exclude(keyword='')
                                
                                for tag in keyword_tags:
                                    if tag.keyword and tag.keyword.lower() in msg_lower:
                                        # Apply tag to user
                                        UserTag.objects.get_or_create(user=existing_user, tag=tag)
                                        webhook_logger.debug(f"Auto-applied tag '{tag.name}' to {phone} (keyword: {tag.keyword})")
                            except Exception as kt_e:
                                webhook_logger.error(f"Keyword tagging error: {kt_e}")
                            # ==================== END KEYWORD MACRO TAGGING ====================

                            bot_response = None
                            trigger = False
                            resp = None


                            # ==================== CALENDLY INTEGRATION ====================
                            # Check for booking/cancellation intent BEFORE calling OpenAI
                            # ONLY for pure text messages (bypass for Images/Docs analyzed by AI)
                            msg_lower = msg_text.lower() if msg_type == 'text' else ""
                            
                            # Booking intent keywords
                            # Booking intent keywords (Strict to avoid collision with 'check-in booking' flow)
                            booking_keywords = ['book appointment', 'schedule a call', 'set up a meeting', 'schedule appointment']
                            
                            # Cancellation intent keywords  
                            cancel_keywords = ['cancel', 'cancel appointment', 'cancel meeting', 
                                             'remove booking', 'delete appointment']
                            
                            is_booking_intent = any(kw in msg_lower for kw in booking_keywords)
                            is_cancel_intent = any(kw in msg_lower for kw in cancel_keywords)
                            
                            if is_booking_intent and not is_cancel_intent:
                                # User wants to book - use admin's configured Calendly URL
                                try:
                                    # Get admin's Calendly settings from database
                                    scheduling_url = getattr(admin_check, 'calendly_scheduling_url', None)
                                    
                                    if scheduling_url and scheduling_url.strip():
                                        bot_response = f"Great! I can help you book an appointment. 📅\n\n"
                                        bot_response += f"👉 Click here to book: {scheduling_url}\n\n"
                                        bot_response += "Choose a time that works best for you!"
                                        trigger = True
                                        webhook_logger.info(f"Calendly booking link sent: {scheduling_url}")
                                    else:
                                        # No Calendly configured - use ChatGPT response
                                        webhook_logger.info("Calendly not configured - using ChatGPT")
                                except Exception as cal_e:
                                    webhook_logger.error(f"Calendly error: {cal_e}")
                                    # Fall through to ChatGPT if Calendly fails
                                    
                            elif is_cancel_intent:
                                # Simple cancel message - direct to email
                                bot_response = "To cancel your appointment, please use the cancellation link in your Calendly confirmation email. 📧\n\nIf you can't find it, check your spam folder or contact us for assistance."
                                trigger = True
                                webhook_logger.info("Calendly cancel guidance sent")
                            # ==================== END CALENDLY INTEGRATION ====================

                            if not trigger:
                                openai_key = creds['openai_key']
                                pine_token = creds['pinecone_token']

                                webhook_logger.debug(f"Processing message from {phone}")
                                
                                if openai_key:
                                    webhook_logger.debug(f"OpenAI key found: {openai_key[:5]}...")
                                    try:
                                        from openai import OpenAI
                                        client = OpenAI(api_key=openai_key)
                                        
                                        # Check for document context for follow-up questions
                                        from newapp.image_pdf_service import get_document_context
                                        doc_context = get_document_context(phone)
                                        context_prefix = ""
                                        if doc_context:
                                            doc_type = doc_context.get('type', 'document')
                                            filename = doc_context.get('filename', '')
                                            analysis = doc_context.get('analysis', '')
                                            context_prefix = f"""[DOCUMENT CONTEXT]
The user recently shared a {doc_type}{' (' + filename + ')' if filename else ''} and you analyzed it.
Here is your previous analysis of that document:
---
{analysis}
---
If the user's question relates to this document, answer based on your analysis above.

"""
                                            webhook_logger.info(f"Using document context for {phone}")
                                        
                                        prompt_obj = None  # Initialize — used later for per-prompt gpt_model
                                        if creds['chatgpt_mode'] == 'ai_agent':
                                            ai_agent = AIAgentConfig.objects.filter(admin=admin_check, is_active=True).last()
                                            pdf_content = ai_agent.pdf_text if ai_agent else ""
                                            instructions = ai_agent.instruction if ai_agent else "Follow the owner's instructions and upload relevant FAQs."
                                            system_prompt = f"{instructions}\n\nREFER TO THE FOLLOWING FAQ/INSTRUCTIONS:\n{pdf_content}"
                                        else:
                                            # Use latest ChatGPT prompt for this org/admin
                                            # Feature 1: Prefer is_default prompt, fallback to latest
                                            if org_check:
                                                prompt_obj = ChatGPTPrompt.objects.filter(organization=org_check, is_default=True).first()
                                                if not prompt_obj:
                                                    prompt_obj = ChatGPTPrompt.objects.filter(organization=org_check).order_by('-updated_at').first()
                                            elif admin_check:
                                                prompt_obj = ChatGPTPrompt.objects.filter(admin=admin_check, is_default=True).first()
                                                if not prompt_obj:
                                                    prompt_obj = ChatGPTPrompt.objects.filter(admin=admin_check).order_by('-updated_at').first()
                                            else:
                                                prompt_obj = None
                                            system_prompt = (
                                                prompt_obj.prompt_text.strip()
                                                if prompt_obj and prompt_obj.prompt_text
                                                else "Follow the admin's instructions to assist the user helpfully."
                                            )
                                            webhook_logger.info(f"Using prompt: id={prompt_obj.id if prompt_obj else 'NONE'} name='{prompt_obj.name if prompt_obj else 'fallback'}' default={prompt_obj.is_default if prompt_obj else 'N/A'}")
                                        
                                        # Add document context to system prompt
                                        if context_prefix:
                                            system_prompt = context_prefix + system_prompt

                                        # --- TOOL INTEGRATION START ---
                                        from newapp.models import ExternalAPI
                                        from newapp.logic import execute_tool, set_current_context
                                        import re
                                        
                                        # Set context for built-in tools like apply_tag
                                        set_current_context(phone, admin_check, org_check)
                                        
                                        # Get tools - check organization first, then admin
                                        if org_check:
                                            db_tools = ExternalAPI.objects.filter(organization=org_check)
                                        else:
                                            db_tools = ExternalAPI.objects.filter(admin=admin_check)
                                        openai_tools = []
                                        if db_tools.exists():
                                            for tool in db_tools:
                                                # Extract parameter names from URL {param} and payload {{param}} placeholders
                                                payload_str = json.dumps(tool.payload or {})
                                                url_str = tool.url or ""
                                                
                                                # Find both {param} (URL path) and {{param}} (payload) placeholders
                                                single_brace_params = re.findall(r'(?<!\{)\{(\w+)\}(?!\})', url_str)
                                                double_brace_params = re.findall(r'\{\{(\w+)\}\}', payload_str + url_str)
                                                param_names = list(set(single_brace_params + double_brace_params))
                                                
                                                # Build dynamic properties from extracted params
                                                if param_names:
                                                    properties = {}
                                                    required_params = []
                                                    for pname in param_names:
                                                        properties[pname] = {
                                                            "type": "string",
                                                            "description": f"The {pname.replace('_', ' ')} value"
                                                        }
                                                        required_params.append(pname)
                                                else:
                                                    # Fallback: allow any parameters
                                                    properties = {
                                                        "data": {
                                                            "type": "object",
                                                            "description": "Data to send to the API"
                                                        }
                                                    }
                                                
                                                openai_tools.append({
                                                    "type": "function",
                                                    "function": {
                                                        "name": tool.name,
                                                        "description": tool.description,
                                                        "parameters": {
                                                            "type": "object",
                                                            "properties": properties,
                                                            "required": required_params if param_names else []
                                                        }
                                                    }
                                                })
                                            webhook_logger.info(f"Registered {len(openai_tools)} External API tool(s)")
                                        
                                        # --- TAG INTEGRATION ---
                                        # Tag is already imported at the top of the file
                                        if org_check:
                                            admin_tags = Tag.objects.filter(organization=org_check)
                                        else:
                                            admin_tags = Tag.objects.filter(admin=admin_check)
                                        
                                        if admin_tags.exists():
                                            # Inject available tags into system prompt
                                            tag_info = "\n\n## AVAILABLE TAGS\nYou can apply the following tags to users using the apply_tag function:\n"
                                            for tag in admin_tags:
                                                tag_info += f"- **{tag.name}** (ID: {tag.id}): {tag.description or 'No description'}\n"
                                            tag_info += "\nWhen you believe a tag matches the user's intent or status, call apply_tag(tag_name='TagName').\n"
                                            system_prompt += tag_info
                                            
                                            # Add apply_custom_field as a built-in tool
                                            openai_tools.append({
                                                "type": "function",
                                                "function": {
                                                    "name": "apply_custom_field",
                                                    "description": "Save or update a custom field value for the current user. Use this to capture user details like name, email, address, phone, etc.",
                                                    "parameters": {
                                                        "type": "object",
                                                        "properties": {
                                                            "field_name": {
                                                                "type": "string",
                                                                "description": "The name of the custom field to update (e.g., name, email, address)"
                                                            },
                                                            "field_value": {
                                                                "type": "string",
                                                                "description": "The value to save for this custom field"
                                                            }
                                                        },
                                                        "required": ["field_name", "field_value"]
                                                    }
                                                }
                                            })

                                            # Add apply_tag as a built-in tool
                                            openai_tools.append({
                                                "type": "function",
                                                "function": {
                                                    "name": "apply_tag",
                                                    "description": "Apply a tag to the current user to categorize them. Use this when the user's intent or status matches a tag.",
                                                    "parameters": {
                                                        "type": "object",
                                                        "properties": {
                                                            "tag_name": {
                                                                "type": "string",
                                                                "description": "The name of the tag to apply to this user"
                                                            }
                                                        },
                                                        "required": ["tag_name"]
                                                    }
                                                }
                                            })
                                            webhook_logger.info(f"Injected {admin_tags.count()} tags + apply_tag tool")
                                                                                # --- CUSTOM FIELD INTEGRATION ---
                                        from newapp.models import CustomField
                                        from newapp.custom_field_processor import format_custom_fields_for_ai_context, get_user_custom_fields
                                        
                                        # Get custom fields for this org/admin
                                        if org_check:
                                            admin_custom_fields = CustomField.objects.filter(organization=org_check, is_active=True)
                                        else:
                                            admin_custom_fields = CustomField.objects.filter(admin=admin_check, is_active=True)
                                        
                                        if admin_custom_fields.exists():
                                            # Get user's existing custom field values
                                            user_custom_fields = get_user_custom_fields(existing_user, admin_check, org_check)
                                            
                                            # Inject available custom fields into system prompt
                                            cf_info = "\n\n## USER CUSTOM FIELDS\nYou can capture the following information from users:\n"
                                            for cf in admin_custom_fields:
                                                cf_info += f"- **{cf.name}** ({cf.field_type}): {cf.description or 'Capture this information'}"
                                                if cf.is_required:
                                                    cf_info += " (Required)"
                                                cf_info += "\n"
                                            cf_info += "\nTo capture a custom field value, output: {{custom_field:field_name:value}}"
                                            cf_info += "\nExample: {{custom_field:name:John Doe}}"
                                            
                                            # Add user's existing values if any
                                            if user_custom_fields:
                                                cf_info += "\n## EXISTING USER DATA"
                                                for field_name, value in user_custom_fields.items():
                                                    cf_info += f"- {field_name}: {value}\n"
                                            
                                            system_prompt += cf_info
                                            
                                            webhook_logger.debug(f"[CustomFields] Injected {admin_custom_fields.count()} custom fields for user {existing_user.phone_no}")# --- END CUSTOM FIELD INTEGRATION ---
                                        # --- LOAD CONVERSATION HISTORY ---
                                        # Get last 20 messages for this user to provide context
                                        chat_history = Message.objects.filter(
                                            user_id=existing_user
                                        ).order_by('-id')[:20]
                                        
                                        # Build messages list with history (oldest first)
                                        openai_messages = [
                                            {"role": "system", "content": system_prompt},
                                        ]
                                        
                                        # Add history in chronological order (reverse since we fetched newest first)
                                        for hist_msg in reversed(list(chat_history)):
                                            role = "assistant" if hist_msg.who == "bot" else "user"
                                            msg_content = hist_msg.messages or ""
                                            if msg_content.strip():
                                                openai_messages.append({"role": role, "content": msg_content})
                                        
                                        # Add current message
                                        openai_messages.append({"role": "user", "content": msg_text})
                                        
                                        webhook_logger.debug(f"[ChatHistory] Loaded {len(openai_messages) - 2} history messages for context")
                                        # --- END CONVERSATION HISTORY ---

                                        # Prepare API Call Params
                                        # Feature 1: Use per-prompt gpt_model if set, otherwise org default
                                        selected_model = creds.get('gpt_model', 'gpt-4o-mini')
                                        if prompt_obj and prompt_obj.gpt_model:
                                            selected_model = prompt_obj.gpt_model
                                        api_params = {
                                            "model": selected_model,
                                            "messages": openai_messages,
                                            "timeout": 30,
                                        }
                                        if openai_tools:
                                            api_params["tools"] = openai_tools
                                            api_params["tool_choice"] = "auto"
                                            
                                        resp = client.chat.completions.create(**api_params)
                                        # Handle Tool Calls
                                        response_message = resp.choices[0].message
                                        
                                        if response_message.tool_calls:
                                            webhook_logger.debug(f"[Tool] AI wants to call {len(response_message.tool_calls)} tools")
                                            # Append the assistant's message (with tool calls) to history
                                            api_params["messages"].append(response_message)
                                            
                                            for tool_call in response_message.tool_calls:
                                                function_name = tool_call.function.name
                                                arguments = json.loads(tool_call.function.arguments)
                                                webhook_logger.debug(f"[Tool] Calling {function_name} with {arguments}")
                                                
                                                # Execute
                                                tool_result = execute_tool(function_name, arguments, admin_check)
                                                
                                                webhook_logger.debug(f"[Tool Result] Output: {tool_result}")
                                                
                                                # Append result
                                                api_params["messages"].append({
                                                    "tool_call_id": tool_call.id,
                                                    "role": "tool",
                                                    "name": function_name,
                                                    "content": tool_result,
                                                })
                                            
                                            # Get Final Response after tools
                                            second_response = client.chat.completions.create(**api_params)
                                            bot_response = (second_response.choices[0].message.content or "").strip()
                                        else:
                                            bot_response = (response_message.content or "").strip()

                                        # --- TOOL INTEGRATION END ---
                                        webhook_logger.debug(f"[Debug] Bot Response generated: {bot_response}")
                                    except Exception as oe:
                                        webhook_logger.error(f"[LLM] OpenAI error details: {str(oe)}", exc_info=True)
                                        resp = None

                                    if bot_response:
                                         webhook_logger.debug("Bot response is valid")
                                    else:
                                         webhook_logger.warning("Bot response is Empty/None")
                                         # BUG FIX: More specific error messages
                                         if not openai_key:
                                             bot_response = "Sorry, my AI assistant is not configured. Please contact support."
                                         elif 'rate_limit' in str(oe).lower() or 'quota' in str(oe).lower():
                                             bot_response = "Sorry, I'm experiencing high demand right now. Please try again in a few moments."
                                         elif 'timeout' in str(oe).lower():
                                             bot_response = "Sorry, the request timed out. Please try again."
                                         else:
                                             bot_response = "Sorry, I encountered an issue processing your request. Please try again."
                                elif pine_token:
                                    try:
                                        pc = Pinecone(api_key=pine_token)
                                        # Use the admin already resolved from webhook metadata
                                        assistant_name = admin_check.assistant_name if admin_check else None
                                        if not assistant_name:
                                            webhook_logger.error("No assistant_name configured for Pinecone")
                                            bot_response = "Sorry, my assistant is not configured yet."
                                            raise Exception("No assistant_name")
                                        assistant = pc.assistant.Assistant(assistant_name=assistant_name)
                                        pmsg = Pinemessage(content=msg_text)
                                        presp = assistant.chat(messages=[pmsg])
                                        bot_response = (presp or {}).get("message", {}).get("content")
                                        webhook_logger.info("Pinecone used for response")
                                    except Exception as pe:
                                        webhook_logger.error(f"Pinecone error: {pe}")
                                        bot_response = "Sorry, I couldn't generate a response just now."
                                else:
                                    bot_response = "Sorry, my assistant is offline right now."

                                if not bot_response:
                                    bot_response = "Got it!"

                            # Safe parsing of AI response
                            final_reply_text = None
                            data_json = None

                            if bot_response:
                                # Strip markdown code fences if present (```json ... ``` or ``` ... ```)
                                cleaned_response = bot_response.strip()
                                if cleaned_response.startswith("```"):
                                    # Remove opening fence (```json or ```)
                                    first_newline = cleaned_response.find("\n")
                                    if first_newline != -1:
                                        cleaned_response = cleaned_response[first_newline + 1:]
                                    # Remove closing fence
                                    if cleaned_response.rstrip().endswith("```"):
                                        cleaned_response = cleaned_response.rstrip()[:-3].rstrip()
                                    bot_response = cleaned_response

                                webhook_logger.debug(f"[JSON Parse] bot_response first 200 chars: {bot_response[:200]}")

                                if bot_response.strip().startswith("{") or bot_response.strip().startswith("["):
                                    try:
                                        data_json = json.loads(bot_response)
                                    except json.JSONDecodeError:
                                        # Try fixing common AI issues: single quotes, trailing commas
                                        try:
                                            import ast
                                            data_json = ast.literal_eval(bot_response)
                                            if isinstance(data_json, dict):
                                                webhook_logger.debug("[JSON Parse] Parsed via ast.literal_eval")
                                            else:
                                                data_json = None
                                        except Exception:
                                            data_json = None

                                    if data_json is not None:
                                        messages = data_json.get("messages", [])
                                        text_parts = []
                                        if messages and isinstance(messages, list):
                                            for msg_item in messages:
                                                if isinstance(msg_item, dict):
                                                    # Try messages[i]["text"] directly
                                                    t = msg_item.get("text")
                                                    if not t:
                                                        # Try messages[i]["message"]["text"]
                                                        t = msg_item.get("message", {}).get("text", "")
                                                    if t and isinstance(t, str) and t.strip():
                                                        text_parts.append(t.strip())
                                        
                                        if text_parts:
                                            final_reply_text = "\n\n".join(text_parts)
                                            webhook_logger.debug(f"[JSON Parse] Extracted {len(text_parts)} text parts from JSON")
                                        else:
                                            final_reply_text = str(bot_response)
                                            webhook_logger.warning("[JSON Parse] JSON parsed but no text found in messages")
                                    else:
                                        # JSON parsing failed completely - try regex fallback
                                        import re
                                        text_matches = re.findall(r'"text"\s*:\s*"((?:[^"\\]|\\.)*)"', bot_response)
                                        if text_matches:
                                            # Unescape JSON string escapes
                                            extracted_texts = []
                                            for t in text_matches:
                                                t = t.replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')
                                                if t.strip():
                                                    extracted_texts.append(t.strip())
                                            if extracted_texts:
                                                final_reply_text = "\n\n".join(extracted_texts)
                                                webhook_logger.debug(f"[JSON Parse] Regex extracted {len(extracted_texts)} text parts")
                                            else:
                                                final_reply_text = str(bot_response)
                                        else:
                                            final_reply_text = str(bot_response)
                                            webhook_logger.warning(f"[JSON Parse] Could not extract text from JSON-like response")
                                else:
                                    final_reply_text = str(bot_response)
                            else:
                                final_reply_text = "Sorry, I couldn't generate a response just now."
                            
                            # --- Add tagging logic here ---
                            tag_keywords = ["active", "priority", "escalation"]
                            if data_json:
                                actions = data_json.get("actions", [])
                                for action in actions:
                                    if action.get("action") == "add_tag":
                                        tag_name = action.get("tag_name", "").lower()
                                        if tag_name in tag_keywords:
                                            tag, _ = Tag.objects.get_or_create(name=tag_name)
                                            if not UserTag.objects.filter(user=existing_user, tag=tag).exists():
                                                UserTag.objects.create(user=existing_user, tag=tag)
                                                webhook_logger.info(f"User {existing_user.id} tagged with {tag_name}")
                            # --- Tagging logic ends here ---



                            # Sending WhatsApp response (with image tag processing)
                            try:
                                # 1. Process Action Tags (Tags & APIs)
                                from newapp.action_tag_processor import process_response_actions
                                
                                action_result = process_response_actions(
                                    final_reply_text,
                                    admin_check,
                                    existing_user.phone_no,
                                    organization=org_check
                                )
                                
                                # Update text with actions removed
                                final_reply_text = action_result.get('final_text', final_reply_text)
                                
                                # Append any API responses to the text
                                api_responses = action_result.get('api_responses', [])
                                if api_responses:
                                    final_reply_text += "\n\n" + "\n".join(api_responses)
                                    
                                webhook_logger.debug(f"Actions executed: {len(action_result.get('actions_executed', []))}")

                                # 2.5 Process Custom Field Tags (after action processing)
                                from newapp.custom_field_processor import process_response_with_custom_fields
                                
                                cf_result = process_response_with_custom_fields(
                                    final_reply_text,
                                    admin_check,
                                    existing_user,
                                    organization=org_check
                                )
                                
                                # Update final_reply_text with custom field tags replaced
                                final_reply_text = cf_result.get('final_text', final_reply_text)
                                
                                if cf_result.get('fields_processed', 0) > 0:
                                    webhook_logger.info(f"Processed {cf_result.get('fields_processed', 0)} custom field(s) for user {existing_user.phone_no}")
                                if cf_result.get('fields_failed', 0) > 0:
                                    webhook_logger.warning(f"Failed to process {cf_result.get('fields_failed', 0)} custom field(s)")

                                # 3. Process Image Tags
                                from newapp.image_tag_processor import process_response_with_images
                                img_result = process_response_with_images(
                                    final_reply_text,
                                    admin_check,
                                    existing_user.phone_no,
                                    phone_number_id,
                                    creds['whatsapp_token'],
                                    organization=org_check
                                )
                                
                                # Update final_reply_text with the processed version (tags removed)
                                final_reply_text = img_result.get('final_text', final_reply_text)
                                
                                webhook_logger.debug(f"Response processed. Images sent: {img_result.get('images_sent', 0)}, Text sent: {img_result.get('text_sent', False)}")
                                
                                if img_result.get('success'):
                                    webhook_logger.info(f"Bot reply sent to {existing_user.phone_no}")
                                else:
                                    webhook_logger.warning(f"Partial success sending to {existing_user.phone_no}")
                                    
                            except Exception as e:
                                webhook_logger.error(f"Sending Exception: {str(e)}", exc_info=True)
                                webhook_logger.error(f"Error in send_whatsapp_message: {e}")
                                
                                # Fallback to regular text sending if image processing fails
                                try:
                                    whatsapp_api_url = f"https://graph.facebook.com/v17.0/{phone_number_id}/messages"
                                    headers = {
                                        "Authorization": f"Bearer {creds['whatsapp_token']}",
                                        "Content-Type": "application/json"
                                    }
                                    payload = {
                                        "messaging_product": "whatsapp",
                                        "to": existing_user.phone_no,
                                        "type": "text",
                                        "text": {"body": final_reply_text}
                                    }
                                    r = requests.post(whatsapp_api_url, json=payload, headers=headers, timeout=15)
                                    if r.status_code == 200:
                                        webhook_logger.info(f"Fallback text sent to {existing_user.phone_no}")
                                except Exception as fallback_e:
                                    webhook_logger.error(f"Fallback failed: {fallback_e}")
                                    
                            if not Message.objects.filter(
                                user_id=existing_user,
                                messages=final_reply_text,
                                who="bot",
                                created_at__gte=timezone.now()-timedelta(seconds=1)
                            ).exists():
                            # Save bot message
                                Message.objects.create(
                                    user_id=existing_user,
                                    messages=final_reply_text,
                                    created_at=timezone.now(),
                                    who="bot"
                                )
                            else:
                                webhook_logger.debug(f"Duplicate bot reply prevented for user: {existing_user.phone_no}")


                            # ===== FOLLOW-UP MESSAGE SCHEDULING =====
                            # Schedule a follow-up message if enabled in settings
                            try:
                                # Get follow-up settings from org or admin
                                followup_enabled = False
                                delay_minutes = 10  # default
                                
                                print(f"[FOLLOWUP DEBUG] org_check={org_check}, admin_check={admin_check}")
                                
                                if org_check:
                                    followup_enabled = getattr(org_check, 'followup_enabled', True)
                                    print(f"[FOLLOWUP DEBUG] org followup_enabled={followup_enabled}")
                                elif admin_check:
                                    followup_enabled = getattr(admin_check, 'followup_enabled', True)
                                    print(f"[FOLLOWUP DEBUG] admin followup_enabled={followup_enabled}")
                                else:
                                    print(f"[FOLLOWUP DEBUG] No org_check or admin_check found!")
                                
                                if followup_enabled:
                                    # PREVENT DUPLICATE FOLLOW-UPS:
                                    # Check if user already has a pending follow-up (followup_count > 0 means one was already scheduled)
                                    # Reset followup_count when user sends a message, so new follow-up can be scheduled
                                    
                                    # Reset followup count since user just messaged (they're active)
                                    if existing_user.followup_count > 0:
                                        existing_user.followup_count = 0
                                        existing_user.save(update_fields=['followup_count'])
                                        webhook_logger.info(f"Reset followup_count for {existing_user.phone_no}")
                                    
                                    # Cancel any pending follow-ups since user just replied
                                    from newapp.models import ScheduledFollowUp
                                    cancelled_count = ScheduledFollowUp.objects.filter(
                                        user=existing_user,
                                        status='pending'
                                    ).update(status='cancelled')
                                    if cancelled_count > 0:
                                        webhook_logger.info(f"Cancelled {cancelled_count} pending follow-up(s) for {existing_user.phone_no}")
                                    
                                    # Check if a follow-up was already scheduled in this conversation window
                                    # Use a timestamp check: only schedule if last bot message was > 30 seconds ago
                                    
                                    recent_bot_msg = Message.objects.filter(
                                        user_id=existing_user,
                                        who='bot',
                                        created_at__gte=timezone.now() - timedelta(seconds=30)
                                    ).count()
                                    
                                    print(f"[FOLLOWUP DEBUG] recent_bot_msg={recent_bot_msg}")
                                    
                                    # If there are multiple bot messages in last 30 sec, skip scheduling
                                    # (prevents duplicate follow-ups from rapid message exchanges)
                                    if recent_bot_msg > 1:
                                        webhook_logger.info(f"Skipping follow-up for {existing_user.phone_no}")
                                        print(f"[FOLLOWUP DEBUG] Skipped: too many recent bot msgs")
                                    else:
                                        # Get delay from FollowUpMessage step 1 (UI settings)
                                        from newapp.models import FollowUpMessage
                                        
                                        # Resolve admin for FollowUpMessage lookup
                                        # If org mode (admin_check is None), fallback to first Admin
                                        followup_admin = admin_check
                                        if not followup_admin and org_check and org_check.whatsapp_phone_id:
                                            followup_admin = Admin.objects.filter(whatsapp_phone_id=org_check.whatsapp_phone_id).first()
                                        
                                        step1_config = FollowUpMessage.objects.filter(
                                            admin=followup_admin,
                                            step=1,
                                            is_active=True
                                        ).first()
                                        
                                        if step1_config:
                                            delay_minutes = step1_config.delay_minutes
                                        else:
                                            # Fall back to org/admin field if no FollowUpMessage configured
                                            if org_check:
                                                delay_minutes = getattr(org_check, 'followup_delay_minutes', 10)
                                            elif admin_check:
                                                delay_minutes = getattr(admin_check, 'followup_delay_minutes', 10)
                                        
                                        delay_seconds = delay_minutes * 60
                                        # Use new persistent scheduling (schedule_followup creates a ScheduledFollowUp record)
                                        print(f"[FOLLOWUP DEBUG] Scheduling follow-up for user {existing_user.id}, delay={delay_minutes}min")
                                        schedule_followup.delay(existing_user.id, step=1)
                                        webhook_logger.info(f"Follow-up scheduled for {existing_user.phone_no}")
                                        print(f"[FOLLOWUP DEBUG] Follow-up scheduled successfully!")
                                else:
                                    webhook_logger.info(f"Follow-ups disabled for {existing_user.phone_no}")
                                    print(f"[FOLLOWUP DEBUG] Follow-ups DISABLED!")
                            except Exception as fu_err:
                                webhook_logger.error(f"Follow-up error: {fu_err}")
                                print(f"[FOLLOWUP DEBUG] EXCEPTION: {fu_err}")
                            # ===== END FOLLOW-UP SCHEDULING =====

                return HttpResponse("Message stored", status=200)

            except Exception as e:
                webhook_logger.error(f"Webhook error: {str(e)}")
                return HttpResponse("OK", status=200)

        return HttpResponse("Method not allowed", status=405)

    # @csrf_exempt
    # def get_message(request):
    #     # SECURITY: Use environment variable for webhook verification
    #     VERIFY_TOKEN = os.environ.get('WHATSAPP_VERIFY_TOKEN', 'speeed')

    #     # Webhook verification
    #     if request.method == 'GET':
    #         mode = request.GET.get('hub.mode')
    #         token = request.GET.get('hub.verify_token')
    #         challenge = request.GET.get('hub.challenge')
    #         if mode == 'subscribe' and token == VERIFY_TOKEN:
    #             return HttpResponse(challenge, status=200)
    #         return HttpResponse("Token verification failed", status=403)

    #     # Webhook delivery
    #     if request.method == 'POST':
    #         try:
    #             data = json.loads(request.body.decode("utf-8"))
    #             webhook_logger.debug(f"Received webhook data: {data}")
    #             # # Extract followup template early
    #             # prompt_obj = ChatGPTPrompt.objects.first()
    #             # prompt_text = (prompt_obj.prompt_text or "").strip() if prompt_obj else ""
    #             # followup_template = whatsappcontroller.extract_followup_message(prompt_text)


    #             entries = data.get('entry') or []
    #             if not entries:
    #                 return HttpResponse("OK", status=200)  # ack silently

    #             for entry in entries:
    #                 changes = entry.get('changes') or []
    #                 for change in changes:
    #                     value = change.get('value') or {}
    #                     metadata = value.get("metadata") or {}
    #                     phone_number_id = metadata.get('phone_number_id')

    #                     # Validate admin
    #                     admin_check = Admin.objects.filter(whatsapp_phone_id=phone_number_id).first()
    #                     if not admin_check:
    #                         continue

    #                     for m in value.get('messages') or []:
    #                         if m.get('type') != 'text':
    #                             continue

    #                         phone = m.get('from')
    #                         msg_text = (m.get('text') or {}).get('body') or ""
    #                         if not msg_text.strip():
    #                             continue
                            
    #                         # 1. Find the profile name in the webhook contacts
    #                         contacts = value.get('contacts', [])
    #                         wa_name = None
    #                         if contacts and len(contacts) > 0:
    #                             wa_name = contacts[0].get('profile', {}).get('name')

    #                         # 2. When creating or updating the user, store the name
    #                         existing_user = User.objects.filter(phone_no=phone).first()
    #                         if not existing_user:
    #                             existing_user = User(
    #                                 phone_no=phone,
    #                                 created_at=datetime.now(),
    #                                 admin_id=Admin.objects.get(id=admin_check.id),
    #                             )

    #                         if wa_name:
    #                             existing_user.name = wa_name

    #                         existing_user.save()


    #                         # Upsert user with timezone aware datetime
    #                         existing_user = User.objects.filter(phone_no=phone).first()
    #                         if not existing_user:
    #                             existing_user = User.objects.create(
    #                                 name='user',
    #                                 admin_id=Admin.objects.get(id=admin_check.id),
    #                                 phone_no=phone,
    #                                 created_at=datetime.now(),
    #                             )

    #                         # Save human message
    #                         try:
    #                             Message.objects.create(
    #                                 user_id=existing_user,
    #                                 messages=msg_text,
    #                                 created_at=datetime.now(),
    #                                 who='human'
    #                             )
    #                         except Exception as db_in_e:
    #                             webhook_logger.error(f"Database inbound error: {db_in_e}")

    #                         # Trigger calendar link
    #                         bot_response = None
    #                         trigger = False
    #                         resp = None
    #                         try:
    #                             if getattr(admin_check, "goolgle_calendar", "") != "":
    #                                 if any(word in msg_text.lower() for word in ['book', 'appointment']):
    #                                     payload = {"msg_text": msg_text.lower(), 'admin_id': admin_check.id, 'user_id': existing_user.id}
    #                                     send_request = requests.post(
    #                                         "https://13e1f2a862ca.ngrok-free.app/send_trigger/",
    #                                         data=payload,
    #                                         timeout=10
    #                                     )
    #                                     send_request.raise_for_status()
    #                                     resp = send_request.json()
    #                                     bot_response = resp.get("url")
    #                                     trigger = True
    #                         except requests.RequestException as e:
    #                             webhook_logger.error(f"Trigger error: {e}")

    #                         # If no trigger, do LLM response
    #                         if not trigger:
    #                             bot_response = None
    #                             openai_key = (getattr(admin_check, "openai_api_key", "") or "").strip()
    #                             pine_token = (getattr(admin_check, "pinecone_token", "") or "").strip()

    #                             if openai_key:
    #                                 try:
    #                                     openai.api_key = openai_key
    #                                     if admin_check.chatgpt_mode == 'ai_agent':
    #                                         ai_agent = AIAgentConfig.objects.filter(admin=admin_check, is_active=True).last()
    #                                         pdf_content = ai_agent.pdf_text if ai_agent else ""
    #                                         instructions = ai_agent.instruction if ai_agent else "Follow the owner's instructions and upload relevant FAQs."
    #                                         system_prompt = f"{instructions}\n\nREFER TO THE FOLLOWING FAQ/INSTRUCTIONS:\n{pdf_content}"
    #                                     else:
    #                                         prompt_obj = ChatGPTPrompt.objects.filter(admin_id=admin_check.id).last()
    #                                         system_prompt = prompt_obj.prompt_text if prompt_obj else "Default prompt."
    #                                     # if not system_prompt:
    #                                     #     system_prompt = (
    #                                     #         "Follow the owner's configured instructions exactly. "
    #                                     #         "If no instructions are configured, reply: 'Prompt not configured.'"
    #                                     #     )
    #                                     resp = openai.ChatCompletion.create(
    #                                         model="gpt-3.5-turbo",
    #                                         messages=[
    #                                             {"role": "system", "content": system_prompt},
    #                                             {"role": "user", "content": msg_text},
    #                                         ],
    #                                         timeout=15,
    #                                     )
    #                                 except Exception as oe:
    #                                     webhook_logger.error(f"OpenAI error: {oe}")
    #                                     resp = None

    #                                 if resp and hasattr(resp, "choices") and len(resp.choices) > 0:
    #                                     bot_response = resp.choices[0].message.content.strip()
    #                                     webhook_logger.info("ChatGPT used for response")
    #                                 else:
    #                                     bot_response = "Sorry, I couldn’t generate a response just now."
    #                             elif pine_token:
    #                                 try:
    #                                     pc = Pinecone(api_key=pine_token)
    #                                     admin = Admin.objects.first()
    #                                     assistant_name = admin.assistant_name  # fetch from your Admin model or relevant object
    #                                     assistant = pc.assistant.Assistant(assistant_name=assistant_name)
    #                                     pmsg = Pinemessage(content=msg_text)
    #                                     presp = assistant.chat(messages=[pmsg])
    #                                     bot_response = (presp or {}).get("message", {}).get("content")
    #                                     webhook_logger.info("Pinecone used for response")
    #                                 except Exception as pe:
    #                                     webhook_logger.error(f"Pinecone error: {pe}")
    #                                     bot_response = "Sorry, I couldn’t generate a response just now."
    #                             else:
    #                                 bot_response = "Sorry, my assistant is offline right now."

    #                             if not bot_response:
    #                                 bot_response = "Got it!"

    #                         # Process JSON response from AI
    #                             try:
    #                                 data_json = None
    #                                 final_reply_text = None

    #                                 if bot_response:
    #                                     try:
    #                                         data_json = json.loads(bot_response)
    #                                     except json.JSONDecodeError:
    #                                         data_json = None

    #                                     if data_json is not None:
    #                                         messages = data_json.get("messages", [])
    #                                         if messages and isinstance(messages, list):
    #                                             final_reply_text = messages[0].get("text") or messages[0].get("message", {}).get("text", "")
    #                                         else:
    #                                             final_reply_text = bot_response
    #                                     else:
    #                                         final_reply_text = bot_response
    #                                 else:
    #                                     final_reply_text = "Sorry, I couldn't generate a response just now."

    #                                 if final_reply_text and isinstance(final_reply_text, str):
    #                                     final_reply_text = final_reply_text.replace("{username}", getattr(existing_user, "name", ""))
    #                                 else:
    #                                     final_reply_text = "Sorry, I couldn't understand your request."
    #                                 # data_json = None
    #                                 # if bot_response:
    #                                 #     try:
    #                                 #         data_json = json.loads(bot_response)
    #                                 #     except json.JSONDecodeError:
    #                                 #         data_json = None
                                            
    #                                 # print("AI response JSON:", data_json)
    #                                 # print("User:", existing_user)
                                
    #                                 # messages = data_json.get("messages", [])
    #                                 # if messages:
    #                                 #     text = messages[0].get("text") or messages[0].get("message", {}).get("text", "")
    #                                 #     if text and isinstance(text, str):
    #                                 #         text = text.replace("{username}", existing_user.name) if hasattr(existing_user, "name") else text
    #                                 #     else:
    #                                 #         text = "Sorry, I couldn't understand your request."
    #                                 # else:
    #                                 #     text = "Sorry, I couldn't understand your request."
    #                                 # final_reply_text = None
    #                                 # if bot_response:
    #                                 #     try:
    #                                 #         data_json = json.loads(bot_response)
    #                                 #         messages = data_json.get("messages", [])
    #                                 #         if messages and isinstance(messages, list):
    #                                 #             final_reply_text = messages[0].get("text") or messages[0].get("message", {}).get("text", "")
    #                                 #         else:
    #                                 #             final_reply_text = bot_response
    #                                 #     except Exception:
    #                                 #         final_reply_text = bot_response
    #                                 # else:
    #                                 #     final_reply_text = "Sorry, I couldn't generate a response just now."

    #                                 # if final_reply_text and isinstance(final_reply_text, str):
    #                                 #     final_reply_text = final_reply_text.replace("{username}", getattr(existing_user, "name", ""))
    #                                 # else:
    #                                 #     final_reply_text = "Sorry, I couldn't understand your request."

                                    
    #                                 tag_keywords = ["active", "priority", "escalation"]
    #                                 actions = data_json.get("actions", [])

    #                                 for action in actions:
    #                                     if action.get("action") == "add_tag":
    #                                         tag_name = action.get("tag_name").lower()
    #                                         if tag_name in tag_keywords:
    #                                             tag, _ = Tag.objects.get_or_create(name=tag_name)
    #                                             if not UserTag.objects.filter(user=existing_user, tag=tag).exists():
    #                                                 UserTag.objects.create(user=existing_user, tag=tag)
    #                                                 webhook_logger.info(f"User {existing_user.id} tagged with {tag_name}")
    #                                 try:
    #                                     r = requests.post(
    #                                         "https://13e1f2a862ca.ngrok-free.app/send_whatsapp_message/",
    #                                         data={
    #                                             "phone": existing_user.phone_no,
    #                                             "message": final_reply_text,
    #                                             "phone_number_id": phone_number_id
    #                                         },
    #                                         timeout=15
    #                                     )
    #                                     if r.status_code != 200:
    #                                         webhook_logger.error(f"send_whatsapp_message error: {r.status_code} - {r.text}")
    #                                 except Exception as e:
    #                                     webhook_logger.error(f"Error in send_whatsapp_message: {e}")

    #                                 Message.objects.create(
    #                                     # user=existing_user,
    #                                     user_id=existing_user,
    #                                     messages=final_reply_text,
    #                                     created_at=datetime.now(),
    #                                     who="bot"
    #                                 )
    #                             # else:
    #                                 # try:
    #                                 #             r = requests.post(
    #                                 #                 "https://64300f6114b3.ngrok-free.app/send_whatsapp_message/",
    #                                 #                 data={
    #                                 #                     "phone": existing_user.phone_no,
    #                                 #                     "message": bot_response,
    #                                 #                     "phone_number_id": phone_number_id
    #                                 #                 },
    #                                 #                 timeout=15
    #                                 #             )
    #                                 #             if r.status_code != 200:
    #                                 #                 webhook_logger.error(f"send_whatsapp_message error: {r.status_code} - {r.text}")
    #                                 # except Exception as e:
    #                                 #             webhook_logger.error(f"Error in send_whatsapp_message: {e}")

    #                                 # Message.objects.create(
    #                                 #             # user=existing_user,
    #                                 #             user_id=existing_user,
    #                                 #             messages=bot_response,
    #                                 #             created_at=datetime.now(),
    #                                 #             who="bot"
    #                                 #         )
    #                                 #  # Schedule follow-up if template exists
    #                                 # if existing_user and followup_template:
    #                                 #     followup_text = followup_template.replace("{username}", existing_user.name)
    #                                 #     send_followup_message.apply_async(args=[existing_user.id, followup_text], countdown=30)
                                     
    #                             except Exception as e:
    #                                 webhook_logger.error(f"Error processing bot response: {e}")

    #             return HttpResponse("Message stored", status=200)

    #         except Exception as e:
    #             webhook_logger.error(f"Webhook error: {str(e)}")
    #             return HttpResponse("OK", status=200)

    #     return HttpResponse("Method not allowed", status=405)

    @csrf_exempt
    def send_trigger(request):
        admin_id=request.POST.get('admin_id') or ''
        user_id=request.POST.get('user_id') or ''
        if user_id=='' or admin_id =='':
            return JsonResponse({'status':False})
        origin = request.build_absolute_uri('/')[:-1]
        # qs=urlencode({'admin_id':admin_id,'user_id':user_id})
        return JsonResponse({
            'status':True,
            'url':f"{origin}/appointment_date/?admin_id={admin_id}&&user_id={user_id}&&calendar_id=aravindkumarpro012@gmail.com"
        })
        # return None
    def appointment_date(request):
        return render(request,'calendar/form.html')
    
    def disconnect(request):
        
        admin_id=request.session.get('admin_id')
        org_id = request.session.get('organization_id')
        
        # Clear Organization WhatsApp credentials (for organization-based auth)
        if org_id:
            from newapp.models import Organization
            Organization.objects.filter(id=org_id).update(whatsapp_phone_id='', whatsapp_token='')
        
        # Also clear Admin WhatsApp credentials (for legacy auth)
        if admin_id:
            Admin.objects.filter(id=admin_id).update(whatsapp_phone_id='', whatsapp_token='')
        
        messages.success(request, 'WhatsApp disconnected successfully')
        return redirect('/setting/channels')
        


    def extract_followup_message(prompt_text):
        marker = "Follow-up message template:"
        idx = prompt_text.find(marker)
        if idx == -1:
            return "Hi {username}, just checking if you need any further assistance. We are here to help!"
        followup_part = prompt_text[idx + len(marker):].strip()
        lines = followup_part.splitlines()
        for line in lines:
            line = line.strip()
            if line:
                return line
        return "Hi {username}, just checking if you need any further assistance. We are here to help!"
