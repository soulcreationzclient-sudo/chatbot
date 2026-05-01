from .models import User, Message, ChatGPTPrompt
# ============================================================================
# BUG FIX: Cleaned up duplicate imports on 2026-02-09
# ============================================================================
from django.db import transaction
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
import json
from django.views.decorators.csrf import csrf_exempt
import requests
from .models import User, Message, Admin, Tag, UserTag
from datetime import datetime
from django.db.models import Max
from django.utils import timezone
from django.contrib import messages
from pinecone_plugins.assistant.models.chat import Message as Pinemessage
from pinecone import Pinecone
import logging

# Initialize logger
logger = logging.getLogger(__name__)











def voice_bot(request):
    return render(request, 'voice_bot.html')



def connect_whatsapp(request):
    if request.method == 'POST':
        token = request.POST.get('token', '').strip()
        phone_id = request.POST.get('phone_id', '').strip()
        waba_id = request.POST.get('waba_id', '').strip()  # Optional WABA ID for template sync
        
        if not token or not phone_id:
            messages.error(request, "Both Access Token and Phone Number ID are required.")
            return render(request, 'connect_whatsapp.html')
        
        # Validate with Facebook Graph API
        import requests as http_requests
        headers = {'Authorization': f"Bearer {token}"}
        url = f"https://graph.facebook.com/v21.0/{phone_id}"
        
        try:
            response = http_requests.get(url, headers=headers)
            response.raise_for_status()
            
            if response.status_code == 200:
                response_data = response.json()
                display_phone_no = str(response_data.get('display_phone_number', ''))
                
                org_id = request.session.get('organization_id')
                admin_id = request.session.get('admin_id')
                
                if org_id:
                    from .models import Organization
                    update_fields = {
                        'whatsapp_phone_id': phone_id,
                        'whatsapp_token': token,
                        'display_phone_no': display_phone_no
                    }
                    if waba_id:
                        update_fields['waba_id'] = waba_id
                    Organization.objects.filter(id=org_id).update(**update_fields)
                    messages.success(request, "WhatsApp connected successfully!")
                    return redirect('dashboard')
                elif admin_id:
                    from .models import Admin
                    Admin.objects.filter(id=admin_id).update(
                        whatsapp_phone_id=phone_id,
                        whatsapp_token=token,
                        display_phone_no=display_phone_no
                    )
                    messages.success(request, "WhatsApp connected successfully!")
                    return redirect('dashboard')
                else:
                    messages.error(request, "Please log in first.")
                    return redirect('login')
                    
        except http_requests.exceptions.RequestException as e:
            messages.error(request, f"WhatsApp connection failed: Invalid credentials or network error.")
            return render(request, 'connect_whatsapp.html')
        
        messages.error(request, "Connection failed. Please try again.")
        return render(request, 'connect_whatsapp.html')
        
    return render(request, 'connect_whatsapp.html')



def send_whatsapp_message(request):
    """
    BUG FIX: Added input validation and proper error handling on 2026-02-09
    """
    response_data = None
    success_message = None
    error_message = None

    # Get credentials from session (FIXED: removed hardcoded credentials)
    token = request.session.get('whatsapp_token')
    phone_id = request.session.get('whatsapp_phone_id')
    
    # Fallback to session-based credentials
    if not token or not phone_id:
        admin_id = request.session.get('admin_id')
        if admin_id:
            admin = Admin.objects.filter(id=admin_id).first()
            if admin:
                token = admin.whatsapp_token
                phone_id = admin.whatsapp_phone_id

    if request.method == 'POST':
        phone = request.POST.get('phone', '').strip()
        message = request.POST.get('message', '').strip()
        
        # BUG FIX: Input validation
        if not phone:
            error_message = "Phone number is required"
            return render(request, 'send_message.html', {'error_message': error_message})
        
        if len(phone) < 10:
            error_message = "Invalid phone number format"
            return render(request, 'send_message.html', {'error_message': error_message})
        
        if not message:
            error_message = "Message content is required"
            return render(request, 'send_message.html', {'error_message': error_message})
        
        if len(message) > 4096:
            error_message = "Message too long (max 4096 characters)"
            return render(request, 'send_message.html', {'error_message': error_message})

        url = f"https://graph.facebook.com/v17.0/{phone_id}/messages"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "text",
            "text": {
                "body": message
            }
        }

        try:
            res = requests.post(url, json=payload, headers=headers)
            response_data = res.json()

            if res.status_code == 200 and "messages" in response_data:
                success_message = "✅ Message sent successfully!"
                
                # BUG FIX: Added transaction management for atomicity
                with transaction.atomic():
                    existing_user = User.objects.filter(phone_no=phone).first()
                    if not existing_user:
                        new_user = User.objects.create(
                            name='bot',
                            phone_no=phone,
                            created_at=timezone.now(),
                            is_in_inbox=True
                        )
                        user_id = new_user.id
                        logger.info(f"New user created: {user_id}")
                    else:
                        user_id = existing_user.id
                        logger.info(f"User already exists: {user_id}")
                    
                    if user_id is not None:
                        user_instance = User.objects.get(id=user_id)
                        new_message = Message.objects.create(
                            user_id=user_instance,
                            messages=message,
                            created_at=timezone.now(),
                            who='bot'
                        )
                        logger.info(f"Message sent successfully to user {user_id}")
            else:
                error_detail = response_data.get(
                    "error", {}).get("message", "Unknown error")
                error_message = f"❌ Failed to send message: {error_detail}"
                logger.error(f"WhatsApp API error: {error_detail}")

        except Exception as e:
            error_message = f"❌ Exception occurred: {str(e)}"
            logger.exception("Error sending WhatsApp message")

    return render(request, 'send_message.html', {
        'response': response_data,
        'success_message': success_message,
        'error_message': error_message
    })

# import requests
# from datetime import datetime
# from django.shortcuts import render
# from django.views.decorators.csrf import csrf_exempt
# from newapp.models import User, Message
# from django.http import HttpResponse

# @csrf_exempt
# def send_whatsapp_message(request):
#     if request.method != 'POST':
#         # Only accept POST requests
#         return HttpResponse("Method not allowed", status=405)

#     phone_number_id = request.POST.get('phone_number_id', '')
#     phone = request.POST.get('phone', '')
#     message = request.POST.get('message', '')
#     response_data = None
#     success_message = None
#     error_message = None

#     if phone == '':
#         return HttpResponse("Phone number missing", status=400)

#     token = Admin.objects.filter(whatsapp_phone_id=phone_number_id).values_list('whatsapp_token', flat=True).first()
#     if token is None or token == '':
#         return HttpResponse("WhatsApp token missing", status=400)

#     url = f"https://graph.facebook.com/v17.0/{phone_number_id}/messages"
#     headers = {
#         "Authorization": f"Bearer {token}",
#         "Content-Type": "application/json"
#     }
#     payload = {
#         "messaging_product": "whatsapp",
#         "to": phone,
#         "type": "text",
#         "text": {"body": message}
#     }

#     try:
#         res = requests.post(url, json=payload, headers=headers)
#         response_data = res.json()

#         if res.status_code == 200 and "messages" in response_data:
#             success_message = "✅ Message sent successfully!"
#             existing_user = User.objects.filter(phone_no=phone).first()
#             if not existing_user:
#                 new_user = User.objects.create(
#                     name='bot',
#                     phone_no=phone,
#                     created_at=datetime.now()
#                 )
#                 user_id = new_user.id
#             else:
#                 user_id = existing_user.id

#             if user_id is not None:
#                 user_instance = User.objects.get(id=user_id)
#                 Message.objects.create(
#                     user_id=user_instance,
#                     messages=message,
#                     created_at=datetime.now(),
#                     who='bot'
#                 )
#         else:
#             error_detail = response_data.get("error", {}).get("message", "Unknown error")
#             error_message = f"❌ Failed to send message: {error_detail}"

#     except Exception as e:
#         error_message = f"❌ Exception occurred: {str(e)}"

#     # Always return an HttpResponse or render at end
#     return render(request, 'send_message.html', {
#         'response': response_data,
#         'success_message': success_message,
#         'error_message': error_message
#     })





def send_voice_bot(request):
    response_data = None
    success_message = None
    error_message = None

    if request.method == 'POST':
        phone = request.POST.get('phone')
        task_message = request.POST.get('message')

        url = "https://us.api.bland.ai/v1/calls"
        headers = {
            "Authorization": "org_75c71ec310d8a684abda84f7449f8d677907dff8520f3be866b24a349d36525a11c4999655477378608569",
            "Content-Type": "application/json"
        }
        payload = {
            "phone_number": phone,
            "task": task_message
        }

        try:
            res = requests.post(url, json=payload, headers=headers)
            response_data = res.json()

            # ✅ Check for success response based on actual API format
            if res.status_code == 200 and response_data.get("status") == "success":
                call_id = response_data.get("call_id", "N/A")
                success_message = f"✅ Voice call queued successfully! Call ID: {call_id}"
            else:
                error_detail = response_data.get("message", "Unknown error")
                error_message = f"❌ Failed to initiate call: {error_detail}"

        except Exception as e:
            error_message = f"❌ Exception occurred: {str(e)}"

    return render(request, 'voice_bot.html', {
        'response': response_data,
        'success_message': success_message,
        'error_message': error_message
    })


def show_people(request):
    org_id = request.session.get('organization_id')
    admin_id = request.session.get('admin_id')
    if org_id:
        users = User.objects.filter(organization_id=org_id).values('id', 'phone_no')
    elif admin_id:
        users = User.objects.filter(admin_id=admin_id).values('id', 'phone_no')
    else:
        users = User.objects.none()
    return render(request, 'show_people.html', {'users': users})


# views.py
def show_chatbox(request):
    org_id = request.session.get('organization_id')
    admin_id = request.session.get('admin_id')
    
    if org_id:
        users = User.objects.filter(organization_id=org_id).only('id', 'phone_no').order_by('id')
    elif admin_id:
        users = User.objects.filter(admin_id=admin_id).only('id', 'phone_no').order_by('id')
    else:
        users = User.objects.none()
        
    selected_user_id = request.GET.get('user_id')

    selected_user = None
    messages = []

    if selected_user_id:
        # Securely fetch user matching org/admin
        if org_id:
            selected_user = User.objects.filter(id=selected_user_id, organization_id=org_id).first()
        elif admin_id:
            selected_user = User.objects.filter(id=selected_user_id, admin_id=admin_id).first()
            
        if selected_user:
            messages = Message.objects.filter(user_id=selected_user_id).order_by('created_at', 'id')

    return render(request, 'show_people.html', {
        'users': users,
        'selected_user': selected_user,
        'messages': messages,
    })


# @csrf_exempt
# def send_whatsapp_message(request):
#     response_data = None
#     token = request.session.get('token')
#     phone_id = request.session.get('phone_id')

#     if request.method == 'POST':
#         phone = request.POST.get('phone')
#         message = request.POST.get('message')

#         url = f"https://graph.facebook.com/v17.0/{phone_id}/messages"
#         headers = {
#             "Authorization": f"Bearer {token}",
#             "Content-Type": "application/json"
#         }
#         payload = {
#             "messaging_product": "whatsapp",
#             "to": phone,
#             "type": "text",
#             "text": {
#                 "body": message
#             }
#         }

#         res = requests.post(url, json=payload, headers=headers)
#         response_data = res.json()

#     return render(request, 'send_message.html', {'response': response_data})


# @csrf_exempt
# def get_message(request):
#     verify_token = "speeed"  # must match what's in Meta dashboard

#     # ✅ Webhook verification (GET)
#     if request.method == 'GET':
#         mode = request.GET.get('hub.mode')
#         token = request.GET.get('hub.verify_token')
#         challenge = request.GET.get('hub.challenge')

#         if mode == 'subscribe' and token == verify_token:
#             return HttpResponse(challenge, status=200)
#         else:
#             return HttpResponse("Token verification failed", status=403)

#     # ✅ Webhook message (POST)
#     elif request.method == 'POST':
#         try:
#             data = json.loads(request.body)
#             # print("Webhook Data:", json.dumps(data, indent=2))

#             entry = data.get('entry', [])[0]
#             changes = entry.get('changes', [])[0]
#             value = changes.get('value', {})
#             messages = value.get('messages', [])[0]

#             phone = messages.get('from')  # WhatsApp number
#             msg_text = messages.get('text', {}).get('body')

#             existing_user = User.objects.filter(phone_no=phone).first()

#             if not existing_user:
#                 existing_user = User.objects.create(
#                     name='user',
#                     phone_no=phone,
#                     created_at=datetime.now()
#                 )
#                 print(f"✅ New user created: {existing_user.id}")

#             Message.objects.create(
#                 user_id=existing_user,
#                 messages=msg_text,
#                 created_at=datetime.now(),
#                 who='human'
#             )

#             pc = Pinecone(
#                 api_key='pcsk_2ayS93_Mo3c98NYEpDXKoSWadNcjjtwAmCPwDJ8Yj3jWHpMhtpvxA5aqSMawtxPYYmRgq1')

#             assistant = pc.assistant.Assistant(assistant_name="yahi")

#             msg = Pinemessage(content=msg_text)
#             resp = assistant.chat(messages=[msg])

#             bot_response = resp["message"]["content"]  # content
#             print(bot_response)
#             phone_number = phone
#             payload = {
#                 "phone": phone_number,
#                 "message": bot_response
#             }
#             response = requests.post(
#                 "https://494b6c088862.ngrok-free.app/send_whatsapp_message/", data=payload)
#             # exit
#             chunks = assistant.chat(messages=[msg], stream=True)


# # With streaming

#             return HttpResponse("Message stored", status=200)

#         except Exception as e:
#             print("Webhook Error:", str(e))
#             return HttpResponse(f"Error: {str(e)}", status=400)


# def broadcast_msg(request):
#     return render(request, 'broadcast_form.html')
def broadcast_msg(request):
    # Filter tags by organization or admin
    org_id = request.session.get('organization_id')
    admin_id = request.session.get('admin_id')
    
    if org_id:
        tags = Tag.objects.filter(organization_id=org_id)
    elif admin_id:
        tags = Tag.objects.filter(admin_id=admin_id)
    else:
        tags = Tag.objects.none()
    
    return render(request, 'broadcast_form.html', {'tags': tags})


# NOTE: WhatsApp credentials are now stored per-org in the database.
# Removed hardcoded WHATSAPP_API_URL and ACCESS_TOKEN for security.


# def send_broadcast(request):
#     if request.method != "POST":
#         return HttpResponse("Invalid request method", status=405)

#     msg = (request.POST.get('message') or '').strip()
#     if not msg:
#         return HttpResponse("Message is required", status=400)

#     # Get all phones you intend to send to
#     phones = list(User.objects.values_list('phone_no', flat=True))
#     users = User.objects.filter(phone_no__in=phones).values('id', 'phone_no')
#     headers = {
#         "Authorization": f"Bearer {ACCESS_TOKEN}",
#         "Content-Type": "application/json"
#     }
#     for user in users:
#         user_instance = User.objects.get(id=user['id'])
#         payload = {
#         "messaging_product": "whatsapp",
#         "to":user['phone_no'],
#         "type": "template",
#         "template": {
#         "name": "hello_world",
#         "language": {"code": "en_US"}
#         }}
#         r = requests.post(WHATSAPP_API_URL, headers=headers, json=payload)
#         Message.objects.create(
#             user_id=user_instance,
#             messages="hello world",
#             who="bot"
#         )
#     return HttpResponse(200)
# NOTE: WhatsApp credentials stored per-org in database (removed hardcoded values)

def send_broadcast(request):
    if request.method != "POST":
        return HttpResponse("Invalid request method", status=405)

    selected_tag_name = request.POST.get('selected_tag_name')
    template_name = request.POST.get('template_name')  # Fixed: was 'template', form sends 'template_name'

    if not selected_tag_name:
        return HttpResponse("Tag selection is required", status=400)
    if not template_name:
        return HttpResponse("Template selection is required", status=400)
    
    # Get organization/admin from session
    org_id = request.session.get('organization_id')
    admin_id = request.session.get('admin_id')
    
    whatsapp_phone_id = None
    whatsapp_token = None
    tag = None
    
    if org_id:
        from .models import Organization
        org = Organization.objects.filter(id=org_id).first()
        if org:
            whatsapp_phone_id = org.whatsapp_phone_id
            whatsapp_token = org.whatsapp_token
        try:
            tag = Tag.objects.get(name=selected_tag_name, organization_id=org_id)
        except Tag.DoesNotExist:
            return HttpResponse(f"Tag '{selected_tag_name}' not found.", status=400)
    elif admin_id:
        admin = Admin.objects.filter(id=admin_id).first()
        if admin:
            whatsapp_phone_id = admin.whatsapp_phone_id
            whatsapp_token = admin.whatsapp_token
        try:
            tag = Tag.objects.get(name=selected_tag_name, admin_id=admin_id)
        except Tag.DoesNotExist:
            return HttpResponse(f"Tag '{selected_tag_name}' not found.", status=400)
    else:
        return HttpResponse("Not authenticated", status=401)
    
    if not whatsapp_phone_id or not whatsapp_token:
        return HttpResponse("WhatsApp not configured", status=403)

    # Get all users linked to the selected tag
    user_ids = UserTag.objects.filter(tag=tag).values_list('user_id', flat=True)
    users = User.objects.filter(id__in=user_ids)
    
    whatsapp_api_url = f"https://graph.facebook.com/v17.0/{whatsapp_phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {whatsapp_token}",
        "Content-Type": "application/json"
    }

    for user in users:
        payload = {
            "messaging_product": "whatsapp",
            "to": user.phone_no,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": "en"}
            }
        }
        r = requests.post(whatsapp_api_url, headers=headers, json=payload)
        logger.info(f"Sent to {user.phone_no}, Status: {r.status_code}")
        
        # Log each message sent in your DB
        Message.objects.create(
            user_id=user,
            messages=f"[Broadcast Template: {template_name}]",
            who="bot",
            created_at=timezone.now()
        )

    # return HttpResponse("Broadcast sent successfully.")
    return redirect('broadcast_msg')

         
   
   
    
    # print(phones)






    return HttpResponse(200,'yahi')

    
    users = User.objects.filter(phone_no__in=phones).values('id', 'phone_no')
    # phone_to_id = {str(u['phone_no']): u['id'] for u in users}

    # headers = {
    #     "Authorization": f"Bearer {ACCESS_TOKEN}",
    #     "Content-Type": "application/json"
    # }

    # results = []
    # messages_to_create = []

    # with transaction.atomic():
    #     for phone in phones:
    #         phone_str = str(phone)

    #         # Send WhatsApp template (hello_world)

    #         }

    #         r = requests.post(WHATSAPP_API_URL, headers=headers, json=payload)
    #         results.append(f"{phone_str}: {r.status_code} {r.text}")

    #         # Find user_id by phone and queue a Message row
    #         user_id = phone_to_id.get(phone_str)
    #         if user_id:
    #             messages_to_create.append(
    #                 Message(
    #                     user_id=user_id,
    #                     messages=msg,          # change to your actual field name if different
    #                     who='bot',             # adjust choices if needed
    #                     created_at=timezone.now(),  # if your model doesn't auto-add
    #                 )
    #             )

    #     # Insert messages in bulk (faster)
    #     if messages_to_create:
    #         Message.objects.bulk_create(messages_to_create, batch_size=500)

    # return HttpResponse("<br>".join(results))
from django.shortcuts import render

# def dashboard_view(request):
#     admin_id=request.session.get('admin_id')
#     # return HttpResponse(admin_id)
#     user=Admin.objects.filter(id=admin_id).only('display_phone_no').first()
#     display_phone_number=''.join((user.display_phone_no).split())
#     # return HttpResponse(display_phone_number)
#     # return HttpResponse(phone_id.whatsapp_phone_id)
#     user_phone=f"https://wa.me/{display_phone_number}"
#     # return HttpResponse(user_phone)
#     count=User.objects.count()
#     return render(request, 'dashboard.html',{'count':count,'phone_id':user_phone})
def dashboard_view(request):
    import json as _json
    from datetime import timedelta
    from django.db.models import Count, Sum, Q
    from django.db.models.functions import TruncDate
    from .models import (
        Organization, User as UserModel, Message,
        Tag, UserTag,
        Opportunity, WebChatSession,
    )

    org_id = request.session.get('organization_id')
    admin_id = request.session.get('admin_id')

    display_phone_number = ''
    whatsapp_connected = False

    # Base querysets scoped by org/admin
    user_qs = UserModel.objects.none()
    msg_qs = Message.objects.none()
    tag_qs = Tag.objects.none()
    opp_qs = Opportunity.objects.none()

    if org_id:
        org = Organization.objects.filter(id=org_id).first()
        if org:
            display_phone_number = ''.join((org.display_phone_no or '').split())
            whatsapp_connected = bool(org.whatsapp_token)
            user_qs = UserModel.objects.filter(organization=org)
            msg_qs = Message.objects.filter(user_id__organization=org)
            tag_qs = Tag.objects.filter(organization_id=org_id)
            opp_qs = Opportunity.objects.filter(organization=org)
    elif admin_id:
        admin_obj = Admin.objects.filter(id=admin_id).first()
        if admin_obj:
            display_phone_number = ''.join((admin_obj.display_phone_no or '').split())
            whatsapp_connected = bool(admin_obj.whatsapp_token)
            user_qs = UserModel.objects.filter(admin_id=admin_obj)
            msg_qs = Message.objects.filter(user_id__admin_id=admin_obj)
            tag_qs = Tag.objects.filter(admin_id=admin_id)
            opp_qs = Opportunity.objects.filter(organization__isnull=True)

    now = timezone.now()

    # ---------- DYNAMIC DATE RANGE ----------
    period = request.GET.get('period', '7d')
    from datetime import datetime as _dtx
    today = now.date()

    if period == 'today':
        range_days = 1
        period_start = timezone.make_aware(_dtx.combine(today, _dtx.min.time()))
        period_end = now
        prev_start = period_start - timedelta(days=1)
        prev_end = period_start
        date_range = [today]
        period_label = 'Today'
    elif period == 'yesterday':
        yesterday = today - timedelta(days=1)
        range_days = 1
        period_start = timezone.make_aware(_dtx.combine(yesterday, _dtx.min.time()))
        period_end = timezone.make_aware(_dtx.combine(today, _dtx.min.time()))
        prev_start = period_start - timedelta(days=1)
        prev_end = period_start
        date_range = [yesterday]
        period_label = 'Yesterday'
    elif period == '30d':
        range_days = 30
        period_start = now - timedelta(days=30)
        period_end = now
        prev_start = now - timedelta(days=60)
        prev_end = period_start
        date_range = [(now - timedelta(days=i)).date() for i in range(29, -1, -1)]
        period_label = 'Last 30 days'
    elif period == 'this_month':
        from calendar import monthrange
        first_of_month = today.replace(day=1)
        range_days = (today - first_of_month).days + 1
        period_start = timezone.make_aware(_dtx.combine(first_of_month, _dtx.min.time()))
        period_end = now
        # Previous period = last month
        last_month_end = first_of_month - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        prev_start = timezone.make_aware(_dtx.combine(last_month_start, _dtx.min.time()))
        prev_end = period_start
        date_range = [(first_of_month + timedelta(days=i)) for i in range(range_days)]
        period_label = 'This Month'
    elif period == 'last_month':
        first_of_this_month = today.replace(day=1)
        last_month_end = first_of_this_month - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        range_days = (last_month_end - last_month_start).days + 1
        period_start = timezone.make_aware(_dtx.combine(last_month_start, _dtx.min.time()))
        period_end = timezone.make_aware(_dtx.combine(first_of_this_month, _dtx.min.time()))
        # Previous period = month before last
        prev_month_end = last_month_start - timedelta(days=1)
        prev_month_start = prev_month_end.replace(day=1)
        prev_start = timezone.make_aware(_dtx.combine(prev_month_start, _dtx.min.time()))
        prev_end = period_start
        date_range = [(last_month_start + timedelta(days=i)) for i in range(range_days)]
        period_label = 'Last Month'
    elif period == 'lifetime':
        # Get earliest message/contact date
        earliest_contact = user_qs.order_by('created_at').values_list('created_at', flat=True).first()
        earliest_msg = msg_qs.order_by('created_at').values_list('created_at', flat=True).first()
        earliest = min(filter(None, [earliest_contact, earliest_msg, now - timedelta(days=90)]))
        range_days = (now - earliest).days + 1
        period_start = earliest
        period_end = now
        prev_start = earliest - timedelta(days=range_days)
        prev_end = earliest
        # For lifetime, group by week if > 60 days, else by day
        if range_days > 60:
            # Show last 90 days max for chart readability
            date_range = [(now - timedelta(days=i)).date() for i in range(min(range_days, 90) - 1, -1, -1)]
        else:
            date_range = [(earliest.date() + timedelta(days=i)) for i in range(range_days)]
        period_label = 'Lifetime'
    else:  # Default: 7d
        period = '7d'
        range_days = 7
        period_start = now - timedelta(days=7)
        period_end = now
        prev_start = now - timedelta(days=14)
        prev_end = period_start
        date_range = [(now - timedelta(days=i)).date() for i in range(6, -1, -1)]
        period_label = 'Last 7 days'

    date_labels = [d.strftime('%b %d') for d in date_range]


    # ---------- KPI CARDS ----------
    total_contacts = user_qs.count()
    new_contacts_period = user_qs.filter(created_at__gte=period_start, created_at__lt=period_end).count()
    new_contacts_prev = user_qs.filter(created_at__gte=prev_start, created_at__lt=prev_end).count()

    total_messages_period = msg_qs.filter(created_at__gte=period_start, created_at__lt=period_end).count()
    total_messages_prev = msg_qs.filter(created_at__gte=prev_start, created_at__lt=prev_end).count()

    active_convos_period = msg_qs.filter(created_at__gte=period_start, created_at__lt=period_end, who='human').values('user_id').distinct().count()
    active_convos_prev = msg_qs.filter(created_at__gte=prev_start, created_at__lt=prev_end, who='human').values('user_id').distinct().count()

    total_bookings = 0
    pipeline_value = opp_qs.filter(status='open').aggregate(total=Sum('opportunity_value'))['total'] or 0

    def _pct_change(current, previous):
        if previous == 0:
            return 100 if current > 0 else 0
        return round(((current - previous) / previous) * 100, 1)

    # ---------- CHART DATA ----------

    # 1) Messages over time — bot vs user
    msg_by_day_user = dict(
        msg_qs.filter(created_at__gte=period_start, created_at__lt=period_end, who='human')
        .annotate(day=TruncDate('created_at'))
        .values('day').annotate(c=Count('id')).values_list('day', 'c')
    )
    msg_by_day_bot = dict(
        msg_qs.filter(created_at__gte=period_start, created_at__lt=period_end, who='bot')
        .annotate(day=TruncDate('created_at'))
        .values('day').annotate(c=Count('id')).values_list('day', 'c')
    )
    chart_msg_user = [msg_by_day_user.get(d, 0) for d in date_range]
    chart_msg_bot = [msg_by_day_bot.get(d, 0) for d in date_range]

    # 2) New contacts over time
    contacts_by_day = dict(
        user_qs.filter(created_at__gte=period_start, created_at__lt=period_end)
        .annotate(day=TruncDate('created_at'))
        .values('day').annotate(c=Count('id')).values_list('day', 'c')
    )
    chart_new_contacts = [contacts_by_day.get(d, 0) for d in date_range]

    # 3) Contacts by channel (WhatsApp vs WebChat)
    webchat_count = user_qs.filter(phone_no__startswith='webchat_').count()
    whatsapp_count = total_contacts - webchat_count

    # 4) Tag distribution (top 8) — count users per tag from actual UserTag table
    user_ids_in_scope = user_qs.values_list('id', flat=True)
    tag_data = list(
        UserTag.objects.filter(user_id__in=user_ids_in_scope)
        .values('tag__name')
        .annotate(count=Count('user_id', distinct=True))
        .order_by('-count')[:8]
    )
    tag_labels = [t['tag__name'] for t in tag_data]
    tag_counts = [t['count'] for t in tag_data]

    # 6) Bot activity (enabled vs disabled)
    bot_on = user_qs.filter(bot_enabled=True).count()
    bot_off = user_qs.filter(bot_enabled=False).count()

    # 7) Total contacts over time (cumulative running total per day)
    total_before_range = user_qs.filter(created_at__lt=date_range[0]).count()
    chart_total_contacts = []
    running = total_before_range
    for d in date_range:
        running += contacts_by_day.get(d, 0)
        chart_total_contacts.append(running)

    # 8) Human vs Bot message totals for doughnut
    total_human_msgs = msg_qs.filter(created_at__gte=period_start, created_at__lt=period_end, who='human').count()
    total_bot_msgs = msg_qs.filter(created_at__gte=period_start, created_at__lt=period_end, who='bot').count()

    # 9) New contacts by channel
    new_webchat_period = user_qs.filter(created_at__gte=period_start, created_at__lt=period_end, phone_no__startswith='webchat_').count()
    new_whatsapp_period = new_contacts_period - new_webchat_period

    # 10) Follow-ups per day
    try:
        from .models import ScheduledFollowUp
        followups_by_day = dict(
            ScheduledFollowUp.objects.filter(
                user__in=user_qs,
                created_at__gte=period_start, created_at__lt=period_end
            ).annotate(day=TruncDate('created_at'))
            .values('day').annotate(c=Count('id')).values_list('day', 'c')
        )
    except Exception:
        followups_by_day = {}
    chart_followups = [followups_by_day.get(d, 0) for d in date_range]

    # 11) Archived contacts per day
    archived_by_day = dict(
        user_qs.filter(archived_at__gte=period_start, archived_at__lt=period_end)
        .annotate(day=TruncDate('archived_at'))
        .values('day').annotate(c=Count('id')).values_list('day', 'c')
    )
    chart_archived = [archived_by_day.get(d, 0) for d in date_range]

    user_phone = f"https://wa.me/{display_phone_number}" if display_phone_number else "#"

    # ---------- ANALYTICS: Optimized batch computation ----------
    from datetime import datetime as _dt
    from django.db.models import F, Min, Max
    from collections import defaultdict

    # Helper: build timezone-aware day boundaries once
    def _day_bounds(d):
        naive = _dt.combine(d, _dt.min.time())
        start = timezone.make_aware(naive) if timezone.is_naive(naive) else naive
        return start, start + timedelta(days=1)

    range_start, _ = _day_bounds(date_range[0])
    _, range_end = _day_bounds(date_range[-1])

    # 12-13) Response time & First response time — BATCH approach (2 queries total)
    # Fetch ALL human and bot messages for the 7-day range in bulk
    all_human = list(
        msg_qs.filter(created_at__gte=range_start, created_at__lt=range_end, who='human')
        .order_by('created_at')
        .values_list('id', 'user_id_id', 'created_at')[:5000]
    )
    all_bot = list(
        msg_qs.filter(created_at__gte=range_start, created_at__lt=range_end, who='bot')
        .order_by('created_at')
        .values_list('id', 'user_id_id', 'created_at')[:5000]
    )

    # Index bot messages by user_id for fast lookup
    bot_by_user = defaultdict(list)
    for _, uid, ts in all_bot:
        bot_by_user[uid].append(ts)

    # Match human→bot pairs: for each human msg, find the next bot msg from same user
    import bisect
    all_response_times = []  # (date, diff_minutes) tuples for all response times
    first_response_by_user_day = {}  # (uid, date) → diff_minutes (first human msg per user per day)

    for _, uid, h_ts in all_human:
        bot_times = bot_by_user.get(uid, [])
        if not bot_times:
            continue
        # Binary search for the first bot reply after this human message
        idx = bisect.bisect_right(bot_times, h_ts)
        if idx < len(bot_times):
            b_ts = bot_times[idx]
            diff_sec = (b_ts - h_ts).total_seconds()
            if 0 < diff_sec < 3600:  # Only count if reply within 1 hour
                diff_min = round(diff_sec / 60.0, 2)
                msg_date = h_ts.date()
                all_response_times.append((msg_date, diff_min))
                # Track first response per user per day
                key = (uid, msg_date)
                if key not in first_response_by_user_day:
                    first_response_by_user_day[key] = diff_min

    # Build per-day chart data
    resp_by_day = defaultdict(list)
    for d, diff in all_response_times:
        resp_by_day[d].append(diff)

    first_resp_by_day = defaultdict(list)
    for (uid, d), diff in first_response_by_user_day.items():
        first_resp_by_day[d].append(diff)

    chart_avg_response = []
    chart_avg_first_response = []
    for d in date_range:
        # Avg response time
        day_resps = resp_by_day.get(d, [])
        avg = round(sum(day_resps) / len(day_resps), 1) if day_resps else 0
        chart_avg_response.append(avg)
        # Avg first response time
        day_firsts = first_resp_by_day.get(d, [])
        avg_first = round(sum(day_firsts) / len(day_firsts), 1) if day_firsts else 0
        chart_avg_first_response.append(avg_first)

    # KPI summary: overall 7-day averages
    all_resp_vals = [v for vals in resp_by_day.values() for v in vals]
    avg_response_time_7d = round(sum(all_resp_vals) / len(all_resp_vals), 1) if all_resp_vals else 0
    all_first_vals = [v for vals in first_resp_by_day.values() for v in vals]
    avg_first_response_7d = round(sum(all_first_vals) / len(all_first_vals), 1) if all_first_vals else 0

    # Previous period response times for period-over-period comparison
    prev_rt_start = prev_start  # Already computed by the dynamic period selector
    prev_rt_end = prev_end
    prev_human = list(
        msg_qs.filter(created_at__gte=prev_rt_start, created_at__lt=prev_rt_end, who='human')
        .order_by('created_at')
        .values_list('id', 'user_id_id', 'created_at')[:3000]
    )
    prev_bot = list(
        msg_qs.filter(created_at__gte=prev_rt_start, created_at__lt=prev_rt_end, who='bot')
        .order_by('created_at')
        .values_list('id', 'user_id_id', 'created_at')[:3000]
    )
    prev_bot_by_user = defaultdict(list)
    for _, uid, ts in prev_bot:
        prev_bot_by_user[uid].append(ts)

    prev_resp_vals = []
    prev_first_by_user = {}
    for _, uid, h_ts in prev_human:
        bot_times = prev_bot_by_user.get(uid, [])
        if not bot_times:
            continue
        idx = bisect.bisect_right(bot_times, h_ts)
        if idx < len(bot_times):
            diff_sec = (bot_times[idx] - h_ts).total_seconds()
            if 0 < diff_sec < 3600:
                diff_min = round(diff_sec / 60.0, 2)
                prev_resp_vals.append(diff_min)
                if uid not in prev_first_by_user:
                    prev_first_by_user[uid] = diff_min

    prev_avg_response = round(sum(prev_resp_vals) / len(prev_resp_vals), 1) if prev_resp_vals else 0
    prev_first_vals = list(prev_first_by_user.values())
    prev_avg_first = round(sum(prev_first_vals) / len(prev_first_vals), 1) if prev_first_vals else 0

    # For response time, lower is better — so invert the change direction
    def _pct_change_inverted(current, previous):
        """For metrics where lower is better (response time). Positive change = improvement."""
        if previous == 0:
            return -100 if current > 0 else 0
        return round(((previous - current) / previous) * 100, 1)

    response_time_change = _pct_change_inverted(avg_response_time_7d, prev_avg_response)
    first_response_change = _pct_change_inverted(avg_first_response_7d, prev_avg_first)

    # 14) Average conversation duration per day (minutes between first and last msg per user)
    chart_avg_duration = []
    for d in date_range:
        day_start, day_end = _day_bounds(d)
        day_msgs = msg_qs.filter(created_at__gte=day_start, created_at__lt=day_end)
        user_durations = day_msgs.values('user_id').annotate(
            first_msg=Min('created_at'), last_msg=Max('created_at')
        ).filter(first_msg__lt=F('last_msg'))
        durations = []
        for ud in user_durations:
            diff = (ud['last_msg'] - ud['first_msg']).total_seconds() / 60.0
            if diff > 0:
                durations.append(diff)
        avg_dur = round(sum(durations) / len(durations), 1) if durations else 0
        chart_avg_duration.append(avg_dur)

    # 15) Bot toggle tracking per day (users currently with bot_enabled=False as proxy for human takeovers)
    bot_toggle_human = bot_off  # Contacts currently handled by human
    bot_toggle_bot = bot_on     # Contacts currently handled by bot

    # 16) New contacts by source
    source_data = list(
        user_qs.filter(created_at__gte=period_start, created_at__lt=period_end)
        .values('source')
        .annotate(count=Count('id'))
        .order_by('-count')[:8]
    )
    source_labels = [s['source'] or 'Unknown' for s in source_data]
    source_counts = [s['count'] for s in source_data]

    # 17) Contacts by country (parse phone number country code prefix)
    COUNTRY_CODES = {
        '1': 'US/CA', '44': 'UK', '91': 'India', '60': 'Malaysia',
        '65': 'Singapore', '61': 'Australia', '971': 'UAE', '966': 'Saudi Arabia',
        '27': 'South Africa', '234': 'Nigeria', '254': 'Kenya',
        '62': 'Indonesia', '63': 'Philippines', '66': 'Thailand',
        '81': 'Japan', '82': 'South Korea', '86': 'China',
        '49': 'Germany', '33': 'France', '39': 'Italy', '34': 'Spain',
        '55': 'Brazil', '52': 'Mexico', '7': 'Russia',
    }
    country_counts = {}
    for u in user_qs.exclude(phone_no__startswith='webchat_').values_list('phone_no', flat=True)[:5000]:
        phone = str(u or '').lstrip('+')
        matched = False
        for code_len in [3, 2, 1]:  # Try longest code first
            prefix = phone[:code_len]
            if prefix in COUNTRY_CODES:
                country = COUNTRY_CODES[prefix]
                country_counts[country] = country_counts.get(country, 0) + 1
                matched = True
                break
        if not matched:
            country_counts['Other'] = country_counts.get('Other', 0) + 1

    sorted_countries = sorted(country_counts.items(), key=lambda x: x[1], reverse=True)[:8]
    country_labels = [c[0] for c in sorted_countries]
    country_values = [c[1] for c in sorted_countries]

    PERIOD_CHOICES = [
        ('today', 'Today'),
        ('yesterday', 'Yesterday'),
        ('7d', 'Last 7 days'),
        ('30d', 'Last 30 days'),
        ('this_month', 'This Month'),
        ('last_month', 'Last Month'),
        ('lifetime', 'Lifetime'),
    ]

    context = {
        'count': total_contacts,
        'phone_id': user_phone,
        'whatsapp_connected': whatsapp_connected,
        # Period selector
        'period': period,
        'period_label': period_label,
        'period_choices': PERIOD_CHOICES,
        # KPI Cards
        'new_contacts_7d': new_contacts_period,
        'new_contacts_change': _pct_change(new_contacts_period, new_contacts_prev),
        'total_messages_7d': total_messages_period,
        'messages_change': _pct_change(total_messages_period, total_messages_prev),
        'active_convos_7d': active_convos_period,
        'active_convos_change': _pct_change(active_convos_period, active_convos_prev),
        'total_bookings': total_bookings,
        'pipeline_value': float(pipeline_value),
        # KPI — Response time
        'avg_response_time_7d': avg_response_time_7d,
        'response_time_change': response_time_change,
        'avg_first_response_7d': avg_first_response_7d,
        'first_response_change': first_response_change,
        # Chart data (JSON)
        'date_labels': _json.dumps(date_labels),
        'chart_msg_user': _json.dumps(chart_msg_user),
        'chart_msg_bot': _json.dumps(chart_msg_bot),
        'chart_new_contacts': _json.dumps(chart_new_contacts),
        'chart_total_contacts': _json.dumps(chart_total_contacts),
        'chart_followups': _json.dumps(chart_followups),
        'chart_archived': _json.dumps(chart_archived),
        'whatsapp_count': whatsapp_count,
        'webchat_count': webchat_count,
        'new_whatsapp_7d': new_whatsapp_period,
        'new_webchat_7d': new_webchat_period,
        'total_human_msgs': total_human_msgs,
        'total_bot_msgs': total_bot_msgs,
        'tag_labels': _json.dumps(tag_labels),
        'tag_counts': _json.dumps(tag_counts),
        'bot_on': bot_on,
        'bot_off': bot_off,
        # Chart analytics data
        'chart_avg_response': _json.dumps(chart_avg_response),
        'chart_avg_first_response': _json.dumps(chart_avg_first_response),
        'chart_avg_duration': _json.dumps(chart_avg_duration),
        'bot_toggle_human': bot_toggle_human,
        'bot_toggle_bot': bot_toggle_bot,
        'source_labels': _json.dumps(source_labels),
        'source_counts': _json.dumps(source_counts),
        'country_labels': _json.dumps(country_labels),
        'country_values': _json.dumps(country_values),
    }
    return render(request, 'dashboard.html', context)


def inbox_view(request):
    return render(request, 'inbox.html')


def flows_view(request):
    return render(request, 'flows.html')

def contacts_view(request):
    return render(request, 'contacts.html')

def settings_view(request):
    return render(request, 'settings.html')




from django.shortcuts import render, redirect
from .forms import TaggingForm
from .models import Tag, User, UserTag

def tag_view(request):
    # Get organization/admin from session
    org_id = request.session.get('organization_id')
    admin_id = request.session.get('admin_id')
    
    if request.method == 'POST':
        form = TaggingForm(request.POST)
        if form.is_valid():
            tag_name = form.cleaned_data['tag_name']
            selected_users = form.cleaned_data['users']
            
            # Create tag with org/admin
            if org_id:
                tag, created = Tag.objects.get_or_create(organization_id=org_id, name=tag_name)
            elif admin_id:
                tag, created = Tag.objects.get_or_create(admin_id=admin_id, name=tag_name)
            else:
                tag, created = Tag.objects.get_or_create(name=tag_name)

            # Delete all existing users from this tag
            UserTag.objects.filter(tag=tag).delete()

            # Add users from submitted form
            for user in selected_users:
                UserTag.objects.get_or_create(user=user, tag=tag)

            return redirect('add_tag')
        else:
            print("Form errors:", form.errors)
    else:
        # Display form for editing or creating
        form = TaggingForm()
        tag_name = request.GET.get('tag_name', None)
        if tag_name:
            if org_id:
                tag = Tag.objects.filter(name=tag_name, organization_id=org_id).first()
            elif admin_id:
                tag = Tag.objects.filter(name=tag_name, admin_id=admin_id).first()
            else:
                tag = Tag.objects.filter(name=tag_name).first()
            if tag:
                users_of_tag = User.objects.filter(usertag__tag=tag)
                form = TaggingForm(initial={
                    'tag_name': tag.name,
                    'users': users_of_tag,
                })
    
    # supply tag_list filtered by org/admin
    tag_list = []
    if org_id:
        tags = Tag.objects.filter(organization_id=org_id)
    elif admin_id:
        tags = Tag.objects.filter(admin_id=admin_id)
    else:
        tags = Tag.objects.none()
    
    for tag in tags:
        tagged_users = User.objects.filter(usertag__tag=tag)
        tag_list.append({'tag': tag, 'users': tagged_users})

    return render(request, 'contact/tag.html', {
        'form': form,
        'tag_list': tag_list,
    })


from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .models import User

@login_required
def user_search_api(request):
    q = request.GET.get('q', '')
    users = User.objects.filter(name__icontains=q)[:20]
    results = [{'id': user.id, 'text': user.name} for user in users]
    return JsonResponse({'items': results})

# google_calendar

import json
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import pytz

# ====== CONFIG ======
SERVICE_ACCOUNT_FILE = "credentials/service-account.json"  # Adjust path
CALENDAR_ID = "aravindkumarpro012@gmail.com"  # Replace with your Google Calendar ID
TIMEZONE = "Asia/Kolkata"
SCOPES = ["https://www.googleapis.com/auth/calendar"]


def get_service():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    return build("calendar", "v3", credentials=creds)


def create_event(date_str, time_str="10:00", title="Appointment", description="", duration_minutes=60):
    service = get_service()
    tz = pytz.timezone(TIMEZONE)
    start_dt = tz.localize(datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M"))
    end_dt = start_dt + timedelta(minutes=duration_minutes)

    event_body = {
        "summary": title,
        "description": description,
        "start": {"dateTime": start_dt.isoformat(), "timeZone": TIMEZONE},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": TIMEZONE},
    }

    event = service.events().insert(calendarId=CALENDAR_ID, body=event_body).execute()
    return event.get('htmlLink')


from django.views.decorators.csrf import csrf_protect
from django.shortcuts import render
# from .google_calendar import create_event  # Import your create_event function from where you defined it


# @csrf_protect
# def create_event_api(request):
#     success_message = None
#     error_message = None

#     if request.method == "POST":
#         date = request.POST.get("date")
#         time = request.POST.get("time", "10:00")
#         title = request.POST.get("title", "Appointment")
#         description = request.POST.get("description", "")
#         duration = request.POST.get("duration", "60")

#         try:
#             duration = int(duration)
#         except ValueError:
#             duration = 60

#         try:
#             event_link = create_event(date, time, title, description, duration)
#             success_message = f"Event '{title}' created successfully! <a href='{event_link}' target='_blank'>View Event</a>"
#         except Exception as e:
#             error_message = f"Failed to create event: {str(e)}"

#     return render(request, 'calendar/form.html', {
#         'success_message': success_message,
#         'error_message': error_message,
#     })

def create_event_api(request):
    success_message = None
    error_message = None

    if request.method == "POST":
        date = request.POST.get("date")
        time = request.POST.get("time", "10:00")
        title = request.POST.get("title", "Appointment")
        description = request.POST.get("description", "")
        duration = request.POST.get("duration", "60")
        user_email = request.POST.get("user_email", "Unknown user")  # <-- get user_email from form
        admin_id = request.POST.get("admin_id", "Unknown admin")
        user_id = request.POST.get("user_id", "Unknown user")

        try:
            duration = int(duration)
        except ValueError:
            duration = 60

        # Append user email to event description
        full_description = f"Created by: {user_email}\n\n{description}"

        try:
            event_link = create_event(date, time, title, full_description, duration)  # use full_description
            success_message = f"Event '{title}' created successfully! <a href='{event_link}' target='_blank'>View Event</a>"
        except Exception as e:
            error_message = f"Failed to create event: {str(e)}"

    return render(request, 'calendar/form.html', {
        'success_message': success_message,
        'error_message': error_message,
        'admin_id': admin_id,
        'user_id': user_id,
        'user_email': user_email,
    })

#chat gpt part
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required  # use if needed
from newapp.models import Admin  # or wherever you store the API keys
import openai


def send_inbox_message(request):
    """Send a message from the inbox to a user via WhatsApp (no AI)"""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    try:
        # Get message and user_id from form data
        message = request.POST.get("message", "").strip()
        user_id = request.POST.get("user_id")
        media_url = request.POST.get("media_url", "").strip()
        media_type = request.POST.get("media_type", "").strip()  # 'image', 'video', 'document'
        
        if not message and not media_url:
            return JsonResponse({"error": "Message cannot be empty."}, status=400)
        if not user_id:
            return JsonResponse({"error": "User ID is required."}, status=400)
        
        # Get organization/admin from session
        org_id = request.session.get('organization_id')
        admin_id = request.session.get('admin_id')
        
        whatsapp_phone_id = None
        whatsapp_token = None
        
        if org_id:
            from .models import Organization
            org = Organization.objects.filter(id=org_id).first()
            if org:
                whatsapp_phone_id = org.whatsapp_phone_id
                whatsapp_token = org.whatsapp_token
        
        if not whatsapp_phone_id and admin_id:
            admin = Admin.objects.filter(id=admin_id).first()
            if admin:
                whatsapp_phone_id = admin.whatsapp_phone_id
                whatsapp_token = admin.whatsapp_token
        
        # Debug: Log which credentials are being used
        print(f"[send_inbox_message] org_id={org_id}, admin_id={admin_id}")
        print(f"[send_inbox_message] Using phone_id: {whatsapp_phone_id[:10] if whatsapp_phone_id else 'NONE'}...")
        
        # No fallback - if no credentials found, return clear error
        if not whatsapp_phone_id or not whatsapp_token:
            return JsonResponse({
                "error": f"WhatsApp not configured for this organization. Please go to Settings > WhatsApp to connect."
            }, status=403)
        
        # Get user object
        user_obj = User.objects.filter(id=user_id).first()
        if not user_obj:
            return JsonResponse({"error": "User not found."}, status=404)
        
        # Check 24-hour window - get user's last inbound message
        from datetime import timedelta
        last_user_msg = Message.objects.filter(
            user_id=user_obj, 
            who='human'  # 'human' = inbound from customer
        ).order_by('-created_at').first()
        
        if last_user_msg:
            time_since_last_msg = timezone.now() - last_user_msg.created_at
            if time_since_last_msg > timedelta(hours=24):
                hours_ago = int(time_since_last_msg.total_seconds() / 3600)
                return JsonResponse({
                    "error": f"24-hour conversation window has expired. User last messaged {hours_ago} hours ago. They must message first to reopen the window.",
                    "window_expired": True,
                    "hours_since_last_message": hours_ago
                }, status=403)
        else:
            # No inbound messages from user ever - window never opened
            return JsonResponse({
                "error": "This user has never messaged you. They must initiate conversation first.",
                "window_expired": True,
                "hours_since_last_message": None
            }, status=403)
        
        # Send message to WhatsApp
        whatsapp_api_url = f"https://graph.facebook.com/v17.0/{whatsapp_phone_id}/messages"
        headers = {
            "Authorization": f"Bearer {whatsapp_token}",
            "Content-Type": "application/json"
        }
        
        # Determine if this is a media message or text message
        if media_url and media_type in ('image', 'video', 'document'):
            # Send as WhatsApp media message (image/document/video)
            if media_type == 'image':
                payload = {
                    "messaging_product": "whatsapp",
                    "to": user_obj.phone_no,
                    "type": "image",
                    "image": {
                        "link": media_url,
                        "caption": message if message else ""
                    }
                }
                db_message = f"[Image: {media_url}]" + (f" {message}" if message else "")
            elif media_type == 'video':
                payload = {
                    "messaging_product": "whatsapp",
                    "to": user_obj.phone_no,
                    "type": "video",
                    "video": {
                        "link": media_url,
                        "caption": message if message else ""
                    }
                }
                db_message = f"[Video: {media_url}]" + (f" {message}" if message else "")
            else:  # document
                payload = {
                    "messaging_product": "whatsapp",
                    "to": user_obj.phone_no,
                    "type": "document",
                    "document": {
                        "link": media_url,
                        "caption": message if message else "",
                        "filename": message if message else "document"
                    }
                }
                db_message = f"[Document: {media_url}]" + (f" {message}" if message else "")
            
            print(f"[send_inbox_message] Sending {media_type} media: {media_url}")
        else:
            # Regular text message
            payload = {
                "messaging_product": "whatsapp",
                "to": user_obj.phone_no,
                "type": "text",
                "text": {"body": message}
            }
            db_message = message
        
        wa_response = requests.post(whatsapp_api_url, json=payload, headers=headers)
        
        if wa_response.status_code != 200:
            print(f"[send_inbox_message] WhatsApp API error: {wa_response.text}")
            return JsonResponse({"error": f"WhatsApp API error: {wa_response.text}"}, status=502)
        
        # Save message to database
        Message.objects.create(
            user_id=user_obj,
            messages=db_message,
            created_at=timezone.now(),
            who='bot'  # 'bot' means from agent/admin side
        )
        
        return JsonResponse({"response": db_message, "success": True})
        
    except Exception as e:
        print(f"send_inbox_message error: {e}")
        return JsonResponse({"error": str(e)}, status=500)




def chatgpt_respond(request):
    """Handle chat from inbox UI - saves messages to DB and sends to WhatsApp"""
    if request.method == "POST":
        try:
            # Handle both JSON and FormData
            if request.content_type == 'application/json':
                data = json.loads(request.body)
                user_prompt = data.get("prompt", "") or data.get("message", "")
                user_id = data.get("user_id")
            else:
                user_prompt = request.POST.get("message", "") or request.POST.get("prompt", "")
                user_id = request.POST.get("user_id")
            
            user_prompt = user_prompt.strip()
            if not user_prompt:
                return JsonResponse({"error": "Message cannot be empty."}, status=400)

            # Get organization/admin from session
            org_id = request.session.get('organization_id')
            admin_id = request.session.get('admin_id')
            
            openai_key = None
            admin = None
            org = None
            whatsapp_phone_id = None
            whatsapp_token = None
            
            if org_id:
                from .models import Organization
                org = Organization.objects.filter(id=org_id).first()
                if org:
                    openai_key = org.openai_api_key
                    whatsapp_phone_id = org.whatsapp_phone_id
                    whatsapp_token = org.whatsapp_token
            
            if not openai_key and admin_id:
                admin = Admin.objects.filter(id=admin_id).first()
                if admin:
                    openai_key = admin.openai_api_key
                    whatsapp_phone_id = admin.whatsapp_phone_id
                    whatsapp_token = admin.whatsapp_token
            
            # No fallback - require proper authentication with credentials
            if not openai_key:
                return JsonResponse({"error": "OpenAI API key not configured. Please set it in Settings > Channels."}, status=400)
            
            # Get user object for saving messages
            user_obj = None
            if user_id:
                user_obj = User.objects.filter(id=user_id).first()
            
            # Save user message to DB
            if user_obj:
                Message.objects.create(
                    user_id=user_obj,
                    messages=user_prompt,
                    created_at=timezone.now(),
                    who='human'
                )
            
            # If no OpenAI key, just save as manual message (no AI response)
            if not openai_key:
                # Send to WhatsApp without AI
                if user_obj and whatsapp_phone_id and whatsapp_token:
                    whatsapp_api_url = f"https://graph.facebook.com/v17.0/{whatsapp_phone_id}/messages"
                    headers = {
                        "Authorization": f"Bearer {whatsapp_token}",
                        "Content-Type": "application/json"
                    }
                    payload = {
                        "messaging_product": "whatsapp",
                        "to": user_obj.phone_no,
                        "type": "text",
                        "text": {"body": user_prompt}
                    }
                    requests.post(whatsapp_api_url, json=payload, headers=headers)
                    
                    # Save as bot message (since it's from agent/admin)
                    Message.objects.create(
                        user_id=user_obj,
                        messages=user_prompt,
                        created_at=timezone.now(),
                        who='bot'
                    )
                    return JsonResponse({"response": "Message sent (no AI configured)"})
                return JsonResponse({"error": "OpenAI API key not configured."}, status=403)

            # Get system prompt — Feature 1: prefer is_default prompt
            if org_id:
                prompt_obj = ChatGPTPrompt.objects.filter(organization_id=org_id, is_default=True).first()
                if not prompt_obj:
                    prompt_obj = ChatGPTPrompt.objects.filter(organization_id=org_id).order_by('-updated_at').first()
            elif admin_id:
                prompt_obj = ChatGPTPrompt.objects.filter(admin_id=admin_id, is_default=True).first()
                if not prompt_obj:
                    prompt_obj = ChatGPTPrompt.objects.filter(admin_id=admin_id).order_by('-updated_at').first()
            else:
                prompt_obj = ChatGPTPrompt.objects.order_by('-updated_at').first()
            system_prompt = prompt_obj.prompt_text if prompt_obj else "You are a helpful assistant."

            # Use new OpenAI v1.0+ API format
            from openai import OpenAI
            client = OpenAI(api_key=openai_key)

            # Load External Tools
            from .models import ExternalAPI
            from .logic import execute_tool
            
            # Get tools for admin or organization
            db_tools = []
            if org_id:
                # For organization users, filter by organization
                db_tools = ExternalAPI.objects.filter(organization_id=org_id)
            elif admin:
                # For legacy admin users, filter by admin
                db_tools = ExternalAPI.objects.filter(admin=admin)

            openai_tools = []
            if db_tools and (hasattr(db_tools, 'exists') and db_tools.exists() or len(db_tools) > 0):
                import re
                for tool in db_tools:
                    # Extract {param} placeholders from URL to build proper parameters schema
                    url_params = re.findall(r'\{(\w+)\}', tool.url)
                    properties = {}
                    required = []
                    for param in url_params:
                        properties[param] = {"type": "string", "description": f"The {param.replace('_', ' ')} value"}
                        required.append(param)
                    
                    if not properties:
                        properties = {"input": {"type": "string", "description": "Input value"}}
                    
                    openai_tools.append({
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": {
                                "type": "object",
                                "properties": properties,
                                "required": required
                            }
                        }
                    })

            # Prepare API Call Params
            # Feature 1: Use per-prompt gpt_model if set
            selected_model = 'gpt-4-turbo'
            if prompt_obj and prompt_obj.gpt_model:
                selected_model = prompt_obj.gpt_model
            api_params = {
                "model": selected_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
            }
            if openai_tools:
                api_params["tools"] = openai_tools
                api_params["tool_choice"] = "auto"

            response = client.chat.completions.create(**api_params)
            response_message = response.choices[0].message

            # Handle Tool Calls
            if response_message.tool_calls:
                api_params["messages"].append(response_message)
                
                for tool_call in response_message.tool_calls:
                    function_name = tool_call.function.name
                    arguments = json.loads(tool_call.function.arguments)
                    
                    tool_result = execute_tool(function_name, arguments, admin)
                    
                    api_params["messages"].append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": tool_result,
                    })
                
                second_response = client.chat.completions.create(**api_params)
                final_content = second_response.choices[0].message.content
            else:
                final_content = response_message.content

            # Save bot response to DB
            if user_obj and final_content:
                Message.objects.create(
                    user_id=user_obj,
                    messages=final_content,
                    created_at=timezone.now(),
                    who='bot'
                )
                
                # Send to WhatsApp
                if whatsapp_phone_id and whatsapp_token:
                    whatsapp_api_url = f"https://graph.facebook.com/v17.0/{whatsapp_phone_id}/messages"
                    headers = {
                        "Authorization": f"Bearer {whatsapp_token}",
                        "Content-Type": "application/json"
                    }
                    payload = {
                        "messaging_product": "whatsapp",
                        "to": user_obj.phone_no,
                        "type": "text",
                        "text": {"body": final_content}
                    }
                    requests.post(whatsapp_api_url, json=payload, headers=headers)

            return JsonResponse({"response": final_content})

        except Exception as e:
            print(f"ChatGPT respond error: {e}")
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid request method."}, status=405)

from django.shortcuts import render, redirect
from .models import ChatGPTPrompt

def chatgpt_prompt_page(request):
    """Multi-prompt management page (Feature 1)."""
    # Get organization/admin from session
    org_id = request.session.get('organization_id')
    admin_id = request.session.get('admin_id')
    
    # Get all prompts for current org/admin
    if org_id:
        prompts = ChatGPTPrompt.objects.filter(organization_id=org_id).order_by('-is_default', '-updated_at')
    elif admin_id:
        prompts = ChatGPTPrompt.objects.filter(admin_id=admin_id).order_by('-is_default', '-updated_at')
    else:
        prompts = ChatGPTPrompt.objects.none()
    
    # Get the default prompt for backward compatibility
    prompt_obj = prompts.filter(is_default=True).first() or prompts.first()
    current_prompt = prompt_obj.prompt_text if prompt_obj else ""

    if request.method == "POST":
        action = request.POST.get('action', 'save')
        prompt_id = request.POST.get('prompt_id')
        new_prompt = request.POST.get("prompt_text", "").strip()
        prompt_name = request.POST.get("prompt_name", "Default Prompt").strip()
        gpt_model = request.POST.get("gpt_model", "").strip()
        set_default = request.POST.get("is_default") == 'on'
        
        if action == 'delete' and prompt_id:
            ChatGPTPrompt.objects.filter(id=prompt_id).delete()
        elif prompt_id:
            # Update existing prompt
            p = ChatGPTPrompt.objects.filter(id=prompt_id).first()
            if p:
                p.prompt_text = new_prompt
                p.name = prompt_name
                p.gpt_model = gpt_model
                p.save()
                if set_default:
                    prompts.exclude(id=p.id).update(is_default=False)
                    p.is_default = True
                    p.save()
        else:
            # Create new prompt
            p = ChatGPTPrompt(
                prompt_text=new_prompt,
                name=prompt_name,
                gpt_model=gpt_model,
                is_default=set_default,
            )
            if org_id:
                p.organization_id = org_id
            elif admin_id:
                p.admin_id = admin_id
            p.save()
            if set_default:
                prompts.exclude(id=p.id).update(is_default=False)
        
        return redirect('integration_view')

    return render(request, 'chatgpt_prompt.html', {
        "prompt": current_prompt,
        "prompts": prompts,
        "current_prompt": prompt_obj,
    })

@csrf_exempt
def get_message_chatgpt(request):
    if request.method != "POST":
        return HttpResponse(status=200)

    try:
        data = json.loads(request.body)
        entry = data.get('entry', [])[0]
        changes = entry.get('changes', [])[0]
        value = changes.get('value', {})
        messages_list = value.get('messages', [])

        if not messages_list:
            return HttpResponse("No messages", status=400)

        messages_data = messages_list[0]
        phone = messages_data.get('from')  # WhatsApp number
        message_type = messages_data.get('type')  # text, image, document, etc.

        # Resolve admin/org from webhook metadata (same pattern as main webhook)
        metadata = value.get("metadata") or {}
        phone_number_id = metadata.get('phone_number_id')
        
        admin = None
        org = None
        openai_key = None
        whatsapp_phone_id = phone_number_id
        whatsapp_token = None
        
        if phone_number_id:
            from .models import Organization
            org = Organization.objects.filter(whatsapp_phone_id=phone_number_id).first()
            admin = Admin.objects.filter(whatsapp_phone_id=phone_number_id).first()
        
        # Get credentials - prefer org, fallback to admin
        if org:
            openai_key = org.openai_api_key
            whatsapp_token = org.whatsapp_token
        elif admin:
            openai_key = admin.openai_api_key
            whatsapp_token = admin.whatsapp_token
        
        if not openai_key:
            return HttpResponse("ChatGPT API key not configured", status=400)

        # Get or create user - properly associate with admin/org
        user_obj, _ = User.objects.get_or_create(
            phone_no=phone,
            defaults={
                'name': 'user',
                'created_at': timezone.now(),
                'is_in_inbox': True,
                'admin_id': admin,
                'organization': org,
            }
        )

        # ==================== IMAGE/PDF ANALYSIS ====================
        # Handle image messages
        if message_type == 'image':
            from .image_pdf_service import analyze_media_message
            
            image_info = messages_data.get('image', {})
            media_id = image_info.get('id')
            caption = image_info.get('caption', 'Please analyze this image and respond based on our conversation context.')
            
            # Save incoming message
            Message.objects.create(
                user_id=user_obj,
                messages=f"[Image] {caption}" if image_info.get('caption') else "[Image sent]",
                created_at=timezone.now(),
                who='human'
            )
            
            # Analyze the image
            reply = analyze_media_message(
                media_id=media_id,
                media_type='image',
                user_question=caption,
                admin=admin,
                organization=org
            )
            
            # Save and send reply
            Message.objects.create(
                user_id=user_obj,
                messages=reply,
                created_at=timezone.now(),
                who='bot'
            )
            
            whatsapp_api_url = f"https://graph.facebook.com/v17.0/{whatsapp_phone_id}/messages"
            headers = {
                "Authorization": f"Bearer {whatsapp_token}",
                "Content-Type": "application/json"
            }
            payload = {
                "messaging_product": "whatsapp",
                "to": phone,
                "type": "text",
                "text": {"body": reply}
            }
            requests.post(whatsapp_api_url, json=payload, headers=headers)
            
            return HttpResponse("Image analyzed", status=200)
        
        # Handle document messages (PDFs)
        elif message_type == 'document':
            from .image_pdf_service import analyze_media_message
            
            doc_info = messages_data.get('document', {})
            media_id = doc_info.get('id')
            mime_type = doc_info.get('mime_type', '')
            filename = doc_info.get('filename', 'document')
            caption = doc_info.get('caption', 'Please analyze this document and tell me what it contains.')
            
            # Save incoming message
            Message.objects.create(
                user_id=user_obj,
                messages=f"[Document: {filename}] {caption}",
                created_at=timezone.now(),
                who='human'
            )
            
            # Analyze the document
            reply = analyze_media_message(
                media_id=media_id,
                media_type='document',
                user_question=caption,
                admin=admin,
                mime_type=mime_type,
                organization=org
            )
            
            # Save and send reply
            Message.objects.create(
                user_id=user_obj,
                messages=reply,
                created_at=timezone.now(),
                who='bot'
            )
            
            whatsapp_api_url = f"https://graph.facebook.com/v17.0/{whatsapp_phone_id}/messages"
            headers = {
                "Authorization": f"Bearer {whatsapp_token}",
                "Content-Type": "application/json"
            }
            payload = {
                "messaging_product": "whatsapp",
                "to": phone,
                "type": "text",
                "text": {"body": reply}
            }
            requests.post(whatsapp_api_url, json=payload, headers=headers)
            
            return HttpResponse("Document analyzed", status=200)
        
        # ==================== TEXT MESSAGE HANDLING ====================
        # Handle regular text messages
        user_text = messages_data.get('text', {}).get('body')
        
        # Save incoming text message
        Message.objects.create(
            user_id=user_obj,
            messages=user_text,
            created_at=timezone.now(),
            who='human'
        )

        # Get system prompt for this org/admin — Feature 1: prefer is_default
        if org:
            prompt_obj = ChatGPTPrompt.objects.filter(organization=org, is_default=True).first()
            if not prompt_obj:
                prompt_obj = ChatGPTPrompt.objects.filter(organization=org).order_by('-updated_at').first()
        elif admin:
            prompt_obj = ChatGPTPrompt.objects.filter(admin=admin, is_default=True).first()
            if not prompt_obj:
                prompt_obj = ChatGPTPrompt.objects.filter(admin=admin).order_by('-updated_at').first()
        else:
            prompt_obj = None
        system_prompt = prompt_obj.prompt_text if prompt_obj else "You are a helpful assistant."

        # Load External Tools for OpenAI function calling
        from .models import ExternalAPI
        from .logic import execute_tool, set_current_context
        from openai import OpenAI
        
        client = OpenAI(api_key=openai_key)
        set_current_context(phone, admin, org)
        
        # Get tools for admin or organization
        db_tools = []
        if org:
            db_tools = ExternalAPI.objects.filter(organization=org)
        elif admin:
            db_tools = ExternalAPI.objects.filter(admin=admin)

        openai_tools = []
        if db_tools.exists():
            import re
            for tool in db_tools:
                # Extract {param} placeholders from URL to build proper parameters schema
                url_params = re.findall(r'\{(\w+)\}', tool.url)
                properties = {}
                required = []
                for param in url_params:
                    properties[param] = {"type": "string", "description": f"The {param.replace('_', ' ')} value"}
                    required.append(param)
                
                # If no URL params found, add a generic one
                if not properties:
                    properties = {"input": {"type": "string", "description": "Input value"}}
                
                openai_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": {
                            "type": "object",
                            "properties": properties,
                            "required": required
                        }
                    }
                })

        # Call OpenAI API with tools
        api_params = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text}
            ],
        }
        if openai_tools:
            api_params["tools"] = openai_tools
            api_params["tool_choice"] = "auto"

        response = client.chat.completions.create(**api_params)
        response_message = response.choices[0].message

        # Handle Tool Calls
        if response_message.tool_calls:
            api_params["messages"].append(response_message)
            
            for tool_call in response_message.tool_calls:
                function_name = tool_call.function.name
                arguments = json.loads(tool_call.function.arguments)
                
                tool_result = execute_tool(function_name, arguments, admin)
                
                api_params["messages"].append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": function_name,
                    "content": tool_result,
                })
            
            second_response = client.chat.completions.create(**api_params)
            reply = second_response.choices[0].message.content
        else:
            reply = response_message.content

        # Process action tags in the AI response: {{calendly:name}}, {{tag:add:x}}, {{api:name}}
        from .action_tag_processor import process_response_actions
        tag_result = process_response_actions(reply, admin, phone, organization=org)
        reply = tag_result['final_text']
        # ==================== END TEXT HANDLING ====================

        # Save reply
        Message.objects.create(
            user_id=user_obj,
            messages=reply,
            created_at=timezone.now(),
            who='bot'
        )

        # Send reply back via WhatsApp
        whatsapp_api_url = f"https://graph.facebook.com/v17.0/{whatsapp_phone_id}/messages"
        headers = {
            "Authorization": f"Bearer {whatsapp_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "text",
            "text": {"body": reply}
        }
        requests.post(whatsapp_api_url, json=payload, headers=headers)

        return HttpResponse("ChatGPT message processed", status=200)

    except Exception as e:
        print(f"ChatGPT webhook error: {str(e)}")
        return HttpResponse(f"Error: {str(e)}", status=400)

from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from .models import Admin



def connect_openai_key(request):
    if request.method == "POST":
        data = json.loads(request.body.decode("utf-8"))
        api_key = data.get("api_key", "").strip()
        gpt_model = data.get("gpt_model", "gpt-4o-mini").strip()
        if not api_key:
            return JsonResponse({"msg": "API key is required."}, status=400)

        org_id = request.session.get('organization_id')
        admin_id = request.session.get('admin_id')
        
        if org_id:
            # Organization-based auth
            from .models import Organization
            org = Organization.objects.filter(id=org_id).first()
            if not org:
                return JsonResponse({"msg": "Organization not found."}, status=404)
            org.pinecone_token = ""
            org.openai_api_key = api_key
            org.gpt_model = gpt_model
            org.save(update_fields=['pinecone_token', 'openai_api_key', 'gpt_model'])
            return JsonResponse({"msg": "ChatGPT API key connected."})
        elif admin_id:
            # Legacy admin-based auth
            admin = Admin.objects.filter(id=admin_id).first()
            if not admin:
                return JsonResponse({"msg": "Admin not found."}, status=404)
            admin.pinecone_token = ""
            admin.openai_api_key = api_key
            admin.save(update_fields=['pinecone_token', 'openai_api_key'])
            return JsonResponse({"msg": "ChatGPT API key connected. Pinecone disconnected."})
        else:
            return JsonResponse({"msg": "Not authenticated."}, status=401)
            
    return JsonResponse({"msg": "Invalid request."}, status=405)


def disconnect_openai_key(request):
    if request.method == "POST":
        org_id = request.session.get('organization_id')
        admin_id = request.session.get('admin_id')
        
        if org_id:
            from .models import Organization
            org = Organization.objects.filter(id=org_id).first()
            if org:
                org.openai_api_key = ""
                org.save(update_fields=['openai_api_key'])
                return JsonResponse({"msg": "ChatGPT API key disconnected."})
        elif admin_id:
            admin = Admin.objects.filter(id=admin_id).first()
            if admin:
                admin.openai_api_key = ""
                admin.save(update_fields=['openai_api_key'])
                return JsonResponse({"msg": "ChatGPT API key disconnected."})
        
        return JsonResponse({"msg": "Not authenticated."}, status=401)
    return JsonResponse({"msg": "Invalid request."}, status=405)


def set_gpt_model(request):
    """Endpoint to update GPT model selection without reconnecting."""
    if request.method == "POST":
        data = json.loads(request.body.decode("utf-8"))
        gpt_model = data.get("gpt_model", "").strip()
        if not gpt_model:
            return JsonResponse({"success": False, "error": "Model name is required."}, status=400)

        org_id = request.session.get('organization_id')
        admin_id = request.session.get('admin_id')

        if org_id:
            from .models import Organization
            org = Organization.objects.filter(id=org_id).first()
            if org:
                org.gpt_model = gpt_model
                org.save(update_fields=['gpt_model'])
                return JsonResponse({"success": True, "model": gpt_model})
        elif admin_id:
            # For legacy admin-based, we can store it in session
            request.session['gpt_model'] = gpt_model
            return JsonResponse({"success": True, "model": gpt_model})

        return JsonResponse({"success": False, "error": "Not authenticated."}, status=401)
    return JsonResponse({"success": False, "error": "Invalid request."}, status=405)

# logger = logging.getLogger(__name__)

# def send_whatsapp_reply(message_text, to_phone, phone_id, token):
#     url = f"https://graph.facebook.com/v17.0/{phone_id}"
#     headers = {
#         "Authorization": f"Bearer {token}",
#         "Content-Type": "application/json"
#     }
#     payload = {
#         "messaging_product": "whatsapp",
#         "to": to_phone,
#         "type": "text",
#         "text": {"body": message_text}
#     }
#     try:
#         response = requests.post(url + '/messages', json=payload, headers=headers)
#         if response.status_code != 200:
#             logger.warning(f"Failed to send WhatsApp message: {response.text}")
#     except Exception as e:
#         logger.error(f"Exception during sending WhatsApp message: {e}")

import logging
import requests
from django.utils import timezone
from newapp.models import User, Message

logger = logging.getLogger(__name__)

def send_whatsapp_reply(message_text, to_phone, phone_id, token):
    url = f"https://graph.facebook.com/v17.0/{phone_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": message_text}
    }
    try:
        response = requests.post(url + '/messages', json=payload, headers=headers)
        if response.status_code != 200:
            logger.warning(f"Failed to send WhatsApp message: {response.text}")
        else:
            # Save bot reply in DB
            user, created = User.objects.get_or_create(phone_no=to_phone, defaults={'name': 'bot', 'created_at': timezone.now(), 'is_in_inbox': True})
            Message.objects.create(user=user, messages=message_text, created_at=timezone.now(), who='bot')
    except Exception as e:
        logger.error(f"Exception during sending WhatsApp message: {e}")


import csv
from django.shortcuts import redirect
from django.contrib import messages
from .models import User, Tag, UserTag, Organization
import traceback

def import_contacts(request):
    try:
        if request.method == 'POST':
            tag_name = request.POST.get('tag_name', '').strip()
            csv_file = request.FILES.get('csv_file')

            # Get organization or admin from session
            org_id = request.session.get('organization_id')
            admin_id_value = request.session.get('admin_id')
            
            org_instance = None
            admin_instance = None
            
            if org_id:
                org_instance = Organization.objects.filter(id=org_id).first()
                if not org_instance:
                    messages.error(request, "Organization not found.")
                    return redirect('login')
            elif admin_id_value:
                try:
                    admin_instance = Admin.objects.get(id=admin_id_value)
                except Admin.DoesNotExist:
                    messages.error(request, "Invalid admin.")
                    return redirect('login')
            else:
                messages.error(request, "You must be logged in.")
                return redirect('login')

            if not tag_name or not csv_file:
                messages.error(request, "Tag name and CSV file are required.")
                return redirect('contact_dashboard')

            # Create/get tag (for org or admin)
            if org_instance:
                tag, created = Tag.objects.get_or_create(organization=org_instance, name=tag_name)
            elif admin_instance:
                tag, created = Tag.objects.get_or_create(admin=admin_instance, name=tag_name)
            else:
                tag, created = Tag.objects.get_or_create(name=tag_name)

            decoded_file = csv_file.read().decode('utf-8-sig').splitlines()
            reader = csv.DictReader(decoded_file)
            
            import_count = 0
            for row in reader:
                name = (row.get('name') or '').strip()
                phone = row.get('phone', '').strip()
                if not phone:
                    continue
                if not name:
                    name = 'Unknown'

                # Create or get User with organization/admin
                user, created = User.objects.get_or_create(
                    phone_no=phone, 
                    defaults={
                        'name': name, 
                        'admin_id': admin_instance,
                        'organization': org_instance,
                        'is_in_inbox': True
                    }
                )

                # Update organization if needed
                if not created and org_instance and user.organization != org_instance:
                    user.organization = org_instance
                    user.save()

                UserTag.objects.get_or_create(user=user, tag=tag)
                import_count += 1

            messages.success(request, f"Imported {import_count} contacts under tag '{tag_name}'.")
            return redirect('contact_dashboard')

        return redirect('contact_dashboard')

    except Exception as e:
            print('IMPORT ERROR:', e)
            print(traceback.format_exc())
            return HttpResponse("Import Error: {}".format(e), status=500)


from django.http import JsonResponse
import requests

def whatsapp_templates(request):
    # Get credentials from admin or organization
    org_id = request.session.get('organization_id')
    admin_id = request.session.get('admin_id')
    
    waba_id = None
    access_token = None
    
    if org_id:
        from newapp.models import Organization
        org = Organization.objects.filter(id=org_id).first()
        if org:
            waba_id = getattr(org, 'waba_id', None) or getattr(org, 'whatsapp_phone_id', None)
            access_token = org.whatsapp_token
    elif admin_id:
        from newapp.models import Admin
        admin = Admin.objects.filter(id=admin_id).first()
        if admin:
            waba_id = getattr(admin, 'waba_id', None) or admin.whatsapp_phone_id
            access_token = admin.whatsapp_token
    
    if not waba_id or not access_token:
        return JsonResponse({"error": "WhatsApp not configured", "templates": []}, status=200)
    
    # Fetch templates from Meta API
    url = f"https://graph.facebook.com/v22.0/{waba_id}/message_templates"
    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            templates = response.json().get("data", [])
            template_names = [t["name"] for t in templates]
            return JsonResponse({"templates": template_names})
        else:
            return JsonResponse({"error": "Failed to fetch templates", "templates": []}, status=200)
    except Exception as e:
        return JsonResponse({"error": str(e), "templates": []}, status=200)
    
from django.shortcuts import redirect, get_object_or_404
from newapp.models import Tag

def delete_tag(request, tag_id):
    if request.method == "POST":
        org_id = request.session.get('organization_id')
        admin_id = request.session.get('admin_id')
        
        tag = get_object_or_404(Tag, id=tag_id)
        
        # Verify ownership
        if org_id and tag.organization_id == org_id:
            tag.delete()
        elif admin_id and tag.admin_id == admin_id:
            tag.delete()
        else:
            # Unauthorized or tag doesn't belong to user
            pass
            
    return redirect('add_tag')

from django.shortcuts import get_object_or_404, redirect
from .models import AIAgentConfig

from django.views.decorators.csrf import csrf_exempt


def delete_pdf(request, pk):
    if request.method == "POST":
        pdf = get_object_or_404(AIAgentConfig, pk=pk)
        pdf.pdf_file.delete()  # Removes the file from storage
        pdf.delete()           # Removes the DB entry
    return redirect('ai_agent_upload')  # Update with your upload view name
