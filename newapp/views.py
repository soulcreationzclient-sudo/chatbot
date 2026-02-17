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


WHATSAPP_API_URL = "https://graph.facebook.com/v22.0/771795822685853/messages"
ACCESS_TOKEN = "EAAb5iwsH0RUBPSENEf1CW3OgMo8bjfQRuG3PT1smRsNEYJWimKVjw0l9zfKLo8009E79YDi5xeNhPuTvNlwc2hZCPXHBKXjUI6ClVvQgFnQJEYPZBwBEJdJh3hr5Hg9W7xm2nMfcVrZBVr68g9Qx1C2Fpd4kUPuN5uER7jMleexmpy0w6B1m5bq4IlYEBMEAgZDZD"  # your WhatsApp Cloud API token


# views.py
# views.py

WHATSAPP_API_URL ="https://graph.facebook.com/v22.0/771795822685853/messages"
ACCESS_TOKEN ='EAAb5iwsH0RUBPSENEf1CW3OgMo8bjfQRuG3PT1smRsNEYJWimKVjw0l9zfKLo8009E79YDi5xeNhPuTvNlwc2hZCPXHBKXjUI6ClVvQgFnQJEYPZBwBEJdJh3hr5Hg9W7xm2nMfcVrZBVr68g9Qx1C2Fpd4kUPuN5uER7jMleexmpy0w6B1m5bq4IlYEBMEAgZDZD'


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
WHATSAPP_API_URL ="https://graph.facebook.com/v22.0/771795822685853/messages"
ACCESS_TOKEN ='EAAb5iwsH0RUBPSENEf1CW3OgMo8bjfQRuG3PT1smRsNEYJWimKVjw0l9zfKLo8009E79YDi5xeNhPuTvNlwc2hZCPXHBKXjUI6ClVvQgFnQJEYPZBwBEJdJh3hr5Hg9W7xm2nMfcVrZBVr68g9Qx1C2Fpd4kUPuN5uER7jMleexmpy0w6B1m5bq4IlYEBMEAgZDZD'

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
    org_id = request.session.get('organization_id')
    admin_id = request.session.get('admin_id')
    
    display_phone_number = ''
    whatsapp_connected = False
    count = 0
    
    if org_id:
        # Organization-based auth
        from .models import Organization
        org = Organization.objects.filter(id=org_id).first()
        if org:
            display_phone_number = ''.join((org.display_phone_no or '').split())
            whatsapp_connected = bool(org.whatsapp_token)
            count = User.objects.filter(organization=org).count()
    elif admin_id:
        # Legacy admin-based auth
        user = Admin.objects.filter(id=admin_id).first()
        if user:
            display_phone_number = ''.join((user.display_phone_no or '').split())
            whatsapp_connected = bool(user.whatsapp_token)
            count = User.objects.filter(admin_id=user).count()
    
    user_phone = f"https://wa.me/{display_phone_number}" if display_phone_number else "#"

    context = {
        'count': count,
        'phone_id': user_phone,
        'whatsapp_connected': whatsapp_connected,
        'active_contacts_count': 0,
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

            # Get system prompt
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
                for tool in db_tools:
                    openai_tools.append({
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "param_name": {"type": "string", "description": "Parameter value"} 
                                },
                                "additionalProperties": True
                            }
                        }
                    })

            # Prepare API Call Params
            api_params = {
                "model": "gpt-4-turbo",
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
    # Get organization/admin from session
    org_id = request.session.get('organization_id')
    admin_id = request.session.get('admin_id')
    
    # Get prompt for current org/admin
    if org_id:
        prompt_obj = ChatGPTPrompt.objects.filter(organization_id=org_id).first()
    elif admin_id:
        prompt_obj = ChatGPTPrompt.objects.filter(admin_id=admin_id).first()
    else:
        prompt_obj = None
    
    current_prompt = prompt_obj.prompt_text if prompt_obj else ""

    if request.method == "POST":
        new_prompt = request.POST.get("prompt_text", "").strip()
        if prompt_obj:
            prompt_obj.prompt_text = new_prompt
            prompt_obj.save()
        else:
            # Create new prompt for this org/admin
            if org_id:
                ChatGPTPrompt.objects.create(prompt_text=new_prompt, organization_id=org_id)
            elif admin_id:
                ChatGPTPrompt.objects.create(prompt_text=new_prompt, admin_id=admin_id)
        return redirect('integration_view')

    return render(request, 'chatgpt_prompt.html', {"prompt": current_prompt})

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
            caption = image_info.get('caption', 'What can you see in this image? Describe it in detail.')
            
            # Save incoming message
            Message.objects.create(
                user_id=user_obj,
                messages=f"[Image] {caption}",
                created_at=timezone.now(),
                who='human'
            )
            
            # Analyze the image
            reply = analyze_media_message(
                media_id=media_id,
                media_type='image',
                user_question=caption,
                admin=admin
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
                mime_type=mime_type
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

        # ==================== CALENDLY INTEGRATION ====================
        # Check for booking/cancellation intent BEFORE calling OpenAI
        user_text_lower = user_text.lower() if user_text else ""
        
        # Booking intent keywords
        booking_keywords = ['book', 'schedule', 'appointment', 'meeting', 'book appointment', 
                           'schedule a call', 'set up a meeting', 'book a call', 'schedule meeting']
        
        # Cancellation intent keywords  
        cancel_keywords = ['cancel', 'cancel appointment', 'cancel meeting', 'remove booking',
                          'delete appointment', 'cancel my appointment']
        
        # Check if user wants to book
        is_booking_intent = any(kw in user_text_lower for kw in booking_keywords)
        is_cancel_intent = any(kw in user_text_lower for kw in cancel_keywords)
        
        if is_booking_intent and not is_cancel_intent:
            # User wants to book - return Calendly booking link
            try:
                from .calendly_service import CalendlyService
                from .calendly_views import CALENDLY_ACCESS_TOKEN
                
                service = CalendlyService(access_token=CALENDLY_ACCESS_TOKEN)
                event_types = service.get_event_types()
                
                if event_types:
                    event_type = event_types[0]  # Get first event type
                    booking_url = event_type.get('scheduling_url')
                    event_name = event_type.get('name')
                    duration = event_type.get('duration')
                    
                    reply = f"Great! I can help you book an appointment. 📅\n\n"
                    reply += f"*{event_name}* ({duration} minutes)\n\n"
                    reply += f"👉 Click here to book: {booking_url}\n\n"
                    reply += "Choose a time that works best for you!"
                else:
                    reply = "I'd love to help you book an appointment, but no appointment slots are currently available. Please try again later or contact us directly."
                    
            except Exception as e:
                print(f"Calendly booking error: {e}")
                reply = "I'd love to help you book an appointment! Please visit our scheduling page or contact us directly to book."
        
        elif is_cancel_intent:
            # User wants to cancel - provide cancellation info
            try:
                from .calendly_service import CalendlyService
                from .calendly_views import CALENDLY_ACCESS_TOKEN
                
                service = CalendlyService(access_token=CALENDLY_ACCESS_TOKEN)
                events = service.get_scheduled_events(status='active')
                
                if events:
                    reply = "To cancel your appointment, please use the cancellation link in your confirmation email, or contact us directly with your appointment details."
                else:
                    reply = "I don't see any upcoming appointments. If you need to cancel an appointment, please contact us with your booking details."
                    
            except Exception as e:
                print(f"Calendly cancel error: {e}")
                reply = "To cancel your appointment, please use the cancellation link in your confirmation email, or contact us directly."
        
        else:
            # No booking/cancel intent - use regular ChatGPT response
            if org:
                prompt_obj = ChatGPTPrompt.objects.filter(organization=org).order_by('-updated_at').first()
            elif admin:
                prompt_obj = ChatGPTPrompt.objects.filter(admin=admin).order_by('-updated_at').first()
            else:
                prompt_obj = None
            common_prompt = prompt_obj.prompt_text if prompt_obj else ""
            
            # Add Calendly context to the system prompt
            calendly_context = """
You are also able to help users book and cancel appointments. 
- If a user wants to book an appointment, tell them you can help and ask them to say "book appointment".
- If a user wants to cancel, tell them to say "cancel appointment" or use the cancellation link in their email.
"""
            
            chatgpt_input = f"{common_prompt}\n{calendly_context}\n\nUser: {user_text}" if common_prompt else f"{calendly_context}\n\nUser: {user_text}"

            # Call OpenAI API
            openai.api_key = openai_key
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[{"role": "user", "content": chatgpt_input}],
            )
            reply = response.choices[0].message.content
        # ==================== END CALENDLY INTEGRATION ====================

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
            org.save(update_fields=['pinecone_token', 'openai_api_key'])
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

# import logging
# import requests

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
