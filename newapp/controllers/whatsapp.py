from django.http import HttpResponse
from django.http import JsonResponse
import requests
from ..models import Admin
from django.shortcuts import redirect
from django.contrib import messages
from newapp.models import User
from django.shortcuts import redirect, render
from pinecone import Pinecone
from pinecone_plugins.assistant.models.chat import Message as Pinemessage
from newapp.models import Message
from django.views.decorators.csrf import csrf_exempt
import json
from datetime import datetime
from urllib.parse import urlencode
from django.utils import timezone
import openai
from newapp.models import ChatGPTPrompt
import logging
import requests
from newapp.views import send_whatsapp_reply
from newapp.models import Tag, UserTag
from newapp.tasks import send_followup_message
from newapp.models import AIAgentConfig
from django.utils import timezone
from datetime import timedelta





class whatsappcontroller:
    @csrf_exempt
    def connect(request):
        phone_id = request.POST.get('phone_id') or ''
        user_token = request.POST.get('user_token') or ''

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
                admin_id = request.session.get('admin_id')
                if admin_id:
                    Admin.objects.filter(id=admin_id).update(
                        whatsapp_phone_id=phone_id,
                        whatsapp_token=user_token,
                        display_phone_no=display_phone_no
                    )
                    messages.success(request, "whatsapp connected")
                    return redirect(request.META.get('HTTP_REFERER', '/'))
                messages.success(request, "whatsapp not connected")
                return redirect(request.META.get('HTTP_REFERER', '/'))
           
        except requests.exceptions.RequestException as e:
            messages.warning(request, "whatsapp error try again later")
            return redirect(request.META.get('HTTP_REFERER', '/'))

        messages.warning(request, "server error")
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

        token = Admin.objects.filter(whatsapp_phone_id=phone_number_id)\
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
                    user = User.objects.create(name='bot', phone_no=phone, created_at=datetime.now())
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
        VERIFY_TOKEN = "speeed"

        if request.method == 'GET':
            mode = request.GET.get('hub.mode')
            token = request.GET.get('hub.verify_token')
            challenge = request.GET.get('hub.challenge')
            if mode == 'subscribe' and token == VERIFY_TOKEN:
                return HttpResponse(challenge, status=200)
            return HttpResponse("Token verification failed", status=403)

        if request.method == 'POST':
            try:
                data = json.loads(request.body.decode("utf-8"))
                print("Received webhook data:", data)

                entries = data.get('entry') or []
                if not entries:
                    return HttpResponse("OK", status=200)  # acknowledge silently

                for entry in entries:
                    changes = entry.get('changes') or []
                    for change in changes:
                        value = change.get('value') or {}
                        metadata = value.get("metadata") or {}
                        phone_number_id = metadata.get('phone_number_id')

                        admin_check = Admin.objects.filter(whatsapp_phone_id=phone_number_id).first()
                        if not admin_check:
                            continue

                        for m in value.get('messages') or []:
                            msg_type = m.get('type')
                            phone = m.get('from')
                            
                            # Get user info from contacts
                            contacts = value.get('contacts', [])
                            wa_name = None
                            if contacts and len(contacts) > 0:
                                wa_name = contacts[0].get('profile', {}).get('name')

                            # Get or create user
                            existing_user = User.objects.filter(phone_no=phone).first()
                            if not existing_user:
                                existing_user = User(
                                    phone_no=phone,
                                    created_at=datetime.now(),
                                    admin_id=admin_check,
                                )
                            if wa_name:
                                existing_user.name = wa_name
                            
                            # Reset follow-up counter when user sends a new message
                            # This ensures follow-ups start from 1st again after user replies
                            existing_user.followup_count = 0
                            existing_user.save()
                            print(f"🔄 Reset follow-up counter for {phone}")
                            
                            # ==================== IMAGE/DOCUMENT HANDLING ====================
                            if msg_type == 'image':
                                from newapp.image_pdf_service import analyze_media_message
                                
                                image_info = m.get('image', {})
                                media_id = image_info.get('id')
                                caption = image_info.get('caption', 'What can you see in this image? Describe it in detail.')
                                
                                # Save incoming message
                                Message.objects.create(
                                    user_id=existing_user,
                                    messages=f"[Image] {caption}",
                                    created_at=timezone.now(),
                                    who='human'
                                )
                                
                                # Analyze the image
                                print(f"[Vision] Analyzing image for {phone}...")
                                reply = analyze_media_message(
                                    media_id=media_id,
                                    media_type='image',
                                    user_question=caption,
                                    admin=admin_check
                                )
                                print(f"[Vision] Analysis complete: {reply[:100]}...")
                                
                                # Store context for follow-up questions
                                from newapp.image_pdf_service import store_document_context
                                store_document_context(phone, reply, 'image')
                                
                                # Save and send reply
                                Message.objects.create(
                                    user_id=existing_user,
                                    messages=reply,
                                    created_at=timezone.now(),
                                    who='bot'
                                )
                                
                                whatsapp_api_url = f"https://graph.facebook.com/v17.0/{phone_number_id}/messages"
                                headers = {
                                    "Authorization": f"Bearer {admin_check.whatsapp_token}",
                                    "Content-Type": "application/json"
                                }
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": phone,
                                    "type": "text",
                                    "text": {"body": reply}
                                }
                                requests.post(whatsapp_api_url, json=payload, headers=headers)
                                print(f"[Vision] Reply sent to {phone}")
                                continue
                            
                            elif msg_type == 'document':
                                from newapp.image_pdf_service import analyze_media_message
                                
                                doc_info = m.get('document', {})
                                media_id = doc_info.get('id')
                                mime_type = doc_info.get('mime_type', '')
                                filename = doc_info.get('filename', 'document')
                                caption = doc_info.get('caption', 'Please analyze this document and tell me what it contains.')
                                
                                # Save incoming message
                                Message.objects.create(
                                    user_id=existing_user,
                                    messages=f"[Document: {filename}] {caption}",
                                    created_at=timezone.now(),
                                    who='human'
                                )
                                
                                # Analyze the document
                                print(f"[Vision] Analyzing document '{filename}' for {phone}...")
                                reply = analyze_media_message(
                                    media_id=media_id,
                                    media_type='document',
                                    user_question=caption,
                                    admin=admin_check,
                                    mime_type=mime_type
                                )
                                print(f"[Vision] Analysis complete: {reply[:100]}...")
                                
                                # Store context for follow-up questions
                                from newapp.image_pdf_service import store_document_context
                                store_document_context(phone, reply, 'document', filename)
                                
                                # Save and send reply
                                Message.objects.create(
                                    user_id=existing_user,
                                    messages=reply,
                                    created_at=timezone.now(),
                                    who='bot'
                                )
                                
                                whatsapp_api_url = f"https://graph.facebook.com/v17.0/{phone_number_id}/messages"
                                headers = {
                                    "Authorization": f"Bearer {admin_check.whatsapp_token}",
                                    "Content-Type": "application/json"
                                }
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": phone,
                                    "type": "text",
                                    "text": {"body": reply}
                                }
                                requests.post(whatsapp_api_url, json=payload, headers=headers)
                                print(f"[Vision] Reply sent to {phone}")
                                continue
                            
                            elif msg_type != 'text':
                                # Skip other message types (audio, video, sticker, etc.)
                                continue
                            # ==================== END IMAGE/DOCUMENT HANDLING ====================

                            msg_text = (m.get('text') or {}).get('body') or ""
                            if not msg_text.strip():
                                continue

                            Message.objects.create(
                                user_id=existing_user,
                                messages=msg_text,
                                created_at=timezone.now(),
                                who='human'
                            ) 

                            bot_response = None
                            trigger = False
                            resp = None

                            # ==================== CALENDLY INTEGRATION ====================
                            # Check for booking/cancellation intent BEFORE calling OpenAI
                            msg_lower = msg_text.lower()
                            
                            # Booking intent keywords
                            booking_keywords = ['book', 'schedule', 'appointment', 'meeting', 
                                              'book appointment', 'schedule a call', 'set up a meeting']
                            
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
                                        print(f"[Calendly] Booking link sent: {scheduling_url}")
                                    else:
                                        # No Calendly configured - use ChatGPT response
                                        print("[Calendly] No scheduling URL configured - falling back to ChatGPT")
                                except Exception as cal_e:
                                    print(f"[Calendly] Error: {cal_e}")
                                    # Fall through to ChatGPT if Calendly fails
                                    
                            elif is_cancel_intent:
                                # Simple cancel message - direct to email
                                bot_response = "To cancel your appointment, please use the cancellation link in your Calendly confirmation email. 📧\n\nIf you can't find it, check your spam folder or contact us for assistance."
                                trigger = True
                                print("[Calendly] Cancel guidance sent")
                            # ==================== END CALENDLY INTEGRATION ====================

                            if not trigger:
                                openai_key = (getattr(admin_check, "openai_api_key", "") or "").strip()
                                pine_token = (getattr(admin_check, "pinecone_token", "") or "").strip()

                                if openai_key:
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
                                            print(f"[Context] Using document context for {phone}")
                                        
                                        if admin_check.chatgpt_mode == 'ai_agent':
                                            ai_agent = AIAgentConfig.objects.filter(admin=admin_check, is_active=True).last()
                                            pdf_content = ai_agent.pdf_text if ai_agent else ""
                                            instructions = ai_agent.instruction if ai_agent else "Follow the owner's instructions and upload relevant FAQs."
                                            system_prompt = f"{instructions}\n\nREFER TO THE FOLLOWING FAQ/INSTRUCTIONS:\n{pdf_content}"
                                        else:
                                            # Use latest ChatGPT prompt (for Prompt Mode)
                                            prompt_obj = ChatGPTPrompt.objects.order_by('-updated_at').first()
                                            system_prompt = (
                                                prompt_obj.prompt_text.strip()
                                                if prompt_obj and prompt_obj.prompt_text
                                                else "Follow the admin's instructions to assist the user helpfully."
                                            )
                                        
                                        # Add document context to system prompt
                                        if context_prefix:
                                            system_prompt = context_prefix + system_prompt

                                        resp = client.chat.completions.create(
                                            model="gpt-3.5-turbo",
                                            messages=[
                                                {"role": "system", "content": system_prompt},
                                                {"role": "user", "content": msg_text},
                                            ],
                                            timeout=15,
                                        )
                                    except Exception as oe:
                                        print(f"[LLM] OpenAI error: {oe}")
                                        resp = None

                                    if resp and hasattr(resp, "choices") and len(resp.choices) > 0:
                                        bot_response = resp.choices[0].message.content.strip()
                                        print("[LLM] ChatGPT used")
                                    else:
                                        bot_response = "Sorry, I couldn’t generate a response just now."
                                elif pine_token:
                                    try:
                                        pc = Pinecone(api_key=pine_token)
                                        admin = Admin.objects.first()
                                        assistant_name = admin.assistant_name
                                        assistant = pc.assistant.Assistant(assistant_name=assistant_name)
                                        pmsg = Pinemessage(content=msg_text)
                                        presp = assistant.chat(messages=[pmsg])
                                        bot_response = (presp or {}).get("message", {}).get("content")
                                        print("[LLM] Pinecone used")
                                    except Exception as pe:
                                        print(f"[LLM] Pinecone error: {pe}")
                                        bot_response = "Sorry, I couldn’t generate a response just now."
                                else:
                                    bot_response = "Sorry, my assistant is offline right now."

                                if not bot_response:
                                    bot_response = "Got it!"

                            # Safe parsing of AI response
                            final_reply_text = None
                            data_json = None

                            if bot_response:
                                if bot_response.strip().startswith("{") or bot_response.strip().startswith("["):
                                    try:
                                        data_json = json.loads(bot_response)
                                    except json.JSONDecodeError:
                                        data_json = None
                                    if data_json is not None:
                                        messages = data_json.get("messages", [])
                                        if messages and isinstance(messages, list) and len(messages) > 0:
                                            final_reply_text = messages[0].get("text") or messages[0].get("message", {}).get("text", "")
                                        else:
                                            final_reply_text = str(bot_response)
                                    else:
                                        final_reply_text = str(bot_response)
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
                                                print(f"User {existing_user.id} tagged with {tag_name}.")
                            # --- Tagging logic ends here ---



                            # Sending WhatsApp response
                            try:
                                # Send directly to WhatsApp API
                                whatsapp_api_url = f"https://graph.facebook.com/v17.0/{phone_number_id}/messages"
                                headers = {
                                    "Authorization": f"Bearer {admin_check.whatsapp_token}",
                                    "Content-Type": "application/json"
                                }
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": existing_user.phone_no,
                                    "type": "text",
                                    "text": {"body": final_reply_text}
                                }
                                r = requests.post(whatsapp_api_url, json=payload, headers=headers, timeout=15)
                                if r.status_code != 200:
                                    print(f"send_whatsapp_message error: {r.status_code} - {r.text}")
                                else:
                                    print(f"✅ Bot reply sent to {existing_user.phone_no}")
                            except Exception as e:
                                print(f"Exception calling send_whatsapp_message: {e}")
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
                                print("Duplicate bot reply prevented for user:", existing_user)

                            # ===== FOLLOW-UP MESSAGE SCHEDULING =====
                            # Schedule a follow-up message if enabled in admin settings
                            try:
                                # Check if follow-ups are enabled for this admin
                                if getattr(admin_check, 'followup_enabled', True):
                                    delay_seconds = getattr(admin_check, 'followup_delay_minutes', 10) * 60
                                    send_followup_message.apply_async(
                                        args=[existing_user.id],
                                        countdown=delay_seconds
                                    )
                                    print(f"✅ Follow-up scheduled for user {existing_user.phone_no} in {delay_seconds}s ({getattr(admin_check, 'followup_delay_minutes', 10)} min)")
                                else:
                                    print(f"⏭️ Follow-ups disabled for admin - skipping for {existing_user.phone_no}")
                            except Exception as fu_err:
                                print(f"❌ Error scheduling follow-up: {fu_err}")
                            # ===== END FOLLOW-UP SCHEDULING =====

                return HttpResponse("Message stored", status=200)

            except Exception as e:
                print(f"Webhook Error: {str(e)}")
                return HttpResponse("OK", status=200)

        return HttpResponse("Method not allowed", status=405)

    # @csrf_exempt
    # def get_message(request):
    #     VERIFY_TOKEN = "speeed"

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
    #             print("Received webhook data:", data)
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
    #                             print(f"DB inbound error: {db_in_e}")

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
    #                             print(f"trigger error: {e}")

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
    #                                     print(f"[LLM] OpenAI error: {oe}")
    #                                     resp = None

    #                                 if resp and hasattr(resp, "choices") and len(resp.choices) > 0:
    #                                     bot_response = resp.choices[0].message.content.strip()
    #                                     print("[LLM] ChatGPT used")
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
    #                                     print("[LLM] Pinecone used")
    #                                 except Exception as pe:
    #                                     print(f"[LLM] Pinecone error: {pe}")
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
    #                                                 print(f"User {existing_user.id} tagged with {tag_name}.")
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
    #                                         print(f"send_whatsapp_message error: {r.status_code} - {r.text}")
    #                                 except Exception as e:
    #                                     print(f"Exception calling send_whatsapp_message: {e}")

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
    #                                 #                 print(f"send_whatsapp_message error: {r.status_code} - {r.text}")
    #                                 # except Exception as e:
    #                                 #             print(f"Exception calling send_whatsapp_message: {e}")

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
    #                                 print(f"Error processing bot response: {e}")

    #             return HttpResponse("Message stored", status=200)

    #         except Exception as e:
    #             print(f"Webhook Error: {str(e)}")
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
        Admin.objects.filter(id=admin_id).update(whatsapp_phone_id='', whatsapp_token='')
        messages.warning(request, 'Invalid email or password')
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
