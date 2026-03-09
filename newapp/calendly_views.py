"""
Calendly API Views for Django Chatbot
Endpoints for booking and canceling appointments via Calendly
"""

import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .calendly_service import CalendlyService, get_calendly_service

# ==================== CONFIGURATION ====================

# Your Calendly Personal Access Token
CALENDLY_ACCESS_TOKEN = "eyJraWQiOiIxY2UxZTEzNjE3ZGNmNzY2YjNjZWJjY2Y4ZGM1YmFmYThhNjVlNjg0MDIzZjdjMzJiZTgzNDliMjM4MDEzNWI0IiwidHlwIjoiUEFUIiwiYWxnIjoiRVMyNTYifQ.eyJpc3MiOiJodHRwczovL2F1dGguY2FsZW5kbHkuY29tIiwiaWF0IjoxNzY1NDQzMDUyLCJqdGkiOiIyMWY1YmIyMC0yNjcxLTQ5MDUtOGRiZS0xMTg3ZDRlYTkwMDMiLCJ1c2VyX3V1aWQiOiI0N2Y2OGNiMi04ODRhLTQ2ZGMtOWIzMC1hNzE1MTZhZTk0ZjIifQ.Gpuvge2TU8AUT31ssVRoVWdJ6FcmS2wehicXP-PAHYWYTpEvdHX-iiWzhn2XOx-olE7_RjPnCnLixxnapk94iw"


def get_service():
    """Get Calendly service instance"""
    return CalendlyService(access_token=CALENDLY_ACCESS_TOKEN)


# ==================== USER INFO ====================

@csrf_exempt
@require_http_methods(["GET"])
def calendly_user_info(request):
    """
    Get current Calendly user info
    
    GET /api/calendly/user/
    """
    try:
        service = get_service()
        user = service.get_current_user()
        return JsonResponse({
            "success": True,
            "user": {
                "name": user.get('name'),
                "email": user.get('email'),
                "timezone": user.get('timezone'),
                "uri": user.get('uri'),
                "scheduling_url": user.get('scheduling_url')
            }
        })
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


# ==================== BOOKING ENDPOINTS ====================

@csrf_exempt
@require_http_methods(["GET"])
def calendly_event_types(request):
    """
    Get all available event types for booking
    
    GET /api/calendly/event-types/
    
    Returns:
        List of event types with name, duration, and scheduling URL
    """
    try:
        service = get_service()
        event_types = service.get_event_types()
        
        formatted_types = []
        for et in event_types:
            formatted_types.append({
                "uri": et.get('uri'),
                "name": et.get('name'),
                "description": et.get('description_plain'),
                "duration": et.get('duration'),
                "scheduling_url": et.get('scheduling_url'),
                "active": et.get('active')
            })
        
        return JsonResponse({
            "success": True,
            "event_types": formatted_types,
            "count": len(formatted_types)
        })
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def calendly_available_times(request):
    """
    Get available time slots for a specific event type
    
    GET /api/calendly/available-times/?event_type_uri=<uri>&days=7
    
    Query Params:
        event_type_uri: URI of the event type
        days: Number of days to look ahead (default: 7)
    """
    try:
        event_type_uri = request.GET.get('event_type_uri')
        days = int(request.GET.get('days', 7))
        
        if not event_type_uri:
            return JsonResponse({
                "success": False, 
                "error": "event_type_uri is required"
            }, status=400)
        
        service = get_service()
        available_times = service.get_available_times(event_type_uri)
        formatted_times = service.format_available_times(available_times)
        
        return JsonResponse({
            "success": True,
            "available_times": [
                {
                    "slot": slot,
                    "start_time": available_times[i]['start_time'],
                    "formatted": formatted_times[i]
                }
                for i, slot in enumerate(available_times)
            ],
            "count": len(available_times)
        })
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def calendly_create_booking(request):
    """
    Create a booking (generate scheduling link)
    
    POST /api/calendly/book/
    
    Body (JSON):
        event_type_uri: URI of the event type to book
        
    Returns:
        booking_url: One-time scheduling link for the invitee
    """
    try:
        data = json.loads(request.body)
        event_type_uri = data.get('event_type_uri')
        
        if not event_type_uri:
            return JsonResponse({
                "success": False,
                "error": "event_type_uri is required"
            }, status=400)
        
        service = get_service()
        result = service.create_booking(
            event_type_uri=event_type_uri,
            start_time=data.get('start_time'),
            invitee_email=data.get('email', ''),
            invitee_name=data.get('name', '')
        )
        
        return JsonResponse({
            "success": True,
            "booking_url": result.get('booking_url'),
            "event_type": result.get('event_type'),
            "message": "Please use this link to complete your booking"
        })
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def calendly_get_booking_link(request):
    """
    Get direct scheduling link for an event type
    
    GET /api/calendly/booking-link/?event_type_uri=<uri>
    
    This is a simpler approach - just returns the scheduling URL
    """
    try:
        event_type_uri = request.GET.get('event_type_uri')
        
        service = get_service()
        event_types = service.get_event_types()
        
        if event_type_uri:
            # Find specific event type
            event_type = next((et for et in event_types if et.get('uri') == event_type_uri), None)
            if event_type:
                return JsonResponse({
                    "success": True,
                    "name": event_type.get('name'),
                    "scheduling_url": event_type.get('scheduling_url'),
                    "duration": event_type.get('duration')
                })
            else:
                return JsonResponse({
                    "success": False,
                    "error": "Event type not found"
                }, status=404)
        else:
            # Return first active event type
            if event_types:
                et = event_types[0]
                return JsonResponse({
                    "success": True,
                    "name": et.get('name'),
                    "scheduling_url": et.get('scheduling_url'),
                    "duration": et.get('duration')
                })
            else:
                return JsonResponse({
                    "success": False,
                    "error": "No event types found"
                }, status=404)
                
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


# ==================== CANCELLATION ENDPOINTS ====================

@csrf_exempt
@require_http_methods(["GET"])
def calendly_scheduled_events(request):
    """
    Get scheduled events (appointments)
    
    GET /api/calendly/scheduled-events/?email=user@example.com&status=active
    
    Query Params:
        email: Optional - filter by invitee email
        status: Optional - 'active' or 'canceled' (default: active)
    """
    try:
        email = request.GET.get('email')
        status = request.GET.get('status', 'active')
        
        service = get_service()
        events = service.get_scheduled_events(invitee_email=email, status=status)
        formatted_events = service.format_scheduled_events(events)
        
        return JsonResponse({
            "success": True,
            "events": formatted_events,
            "count": len(formatted_events)
        })
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def calendly_cancel_event(request):
    """
    Cancel a scheduled event
    
    POST /api/calendly/cancel/
    
    Body (JSON):
        event_uuid: UUID of the event to cancel
        reason: Optional cancellation reason
    """
    try:
        data = json.loads(request.body)
        event_uuid = data.get('event_uuid')
        reason = data.get('reason', 'Cancelled via chatbot')
        
        if not event_uuid:
            return JsonResponse({
                "success": False,
                "error": "event_uuid is required"
            }, status=400)
        
        service = get_service()
        result = service.cancel_event(event_uuid, reason)
        
        return JsonResponse({
            "success": True,
            "message": result.get('message'),
            "status": "cancelled"
        })
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


# ==================== CHATBOT INTEGRATION ====================

@csrf_exempt
@require_http_methods(["POST"])
def calendly_chatbot_handler(request):
    """
    Unified endpoint for chatbot integration
    Handles both booking and cancellation intents
    
    POST /api/calendly/chatbot/
    
    Body (JSON):
        action: 'book', 'cancel', 'list_events', 'list_types'
        ... additional params based on action
    """
    try:
        data = json.loads(request.body)
        action = data.get('action', '').lower()
        service = get_service()
        
        if action == 'list_types':
            # Get available event types for booking
            event_types = service.get_event_types()
            return JsonResponse({
                "success": True,
                "action": "list_types",
                "message": "Here are the available appointment types:",
                "event_types": [
                    {
                        "name": et.get('name'),
                        "duration": et.get('duration'),
                        "uri": et.get('uri'),
                        "scheduling_url": et.get('scheduling_url')
                    }
                    for et in event_types
                ]
            })
        
        elif action == 'book':
            # Get booking link
            event_type_uri = data.get('event_type_uri')
            if event_type_uri:
                result = service.create_booking(
                    event_type_uri=event_type_uri,
                    start_time='',
                    invitee_email=data.get('email', ''),
                    invitee_name=data.get('name', '')
                )
                return JsonResponse({
                    "success": True,
                    "action": "book",
                    "message": "Great! Please use this link to book your appointment:",
                    "booking_url": result.get('booking_url')
                })
            else:
                # Return first event type's scheduling URL
                event_types = service.get_event_types()
                if event_types:
                    return JsonResponse({
                        "success": True,
                        "action": "book",
                        "message": f"Great! You can book a {event_types[0].get('name')} here:",
                        "booking_url": event_types[0].get('scheduling_url')
                    })
        
        elif action == 'list_events':
            # List user's scheduled events
            email = data.get('email')
            events = service.get_scheduled_events(invitee_email=email, status='active')
            formatted = service.format_scheduled_events(events)
            
            if formatted:
                return JsonResponse({
                    "success": True,
                    "action": "list_events",
                    "message": "Here are your upcoming appointments:",
                    "events": formatted
                })
            else:
                return JsonResponse({
                    "success": True,
                    "action": "list_events",
                    "message": "You don't have any upcoming appointments.",
                    "events": []
                })
        
        elif action == 'cancel':
            # Cancel an event
            event_uuid = data.get('event_uuid')
            reason = data.get('reason', 'Cancelled via chatbot')
            
            if not event_uuid:
                return JsonResponse({
                    "success": False,
                    "error": "Please specify which appointment to cancel (event_uuid required)"
                }, status=400)
            
            result = service.cancel_event(event_uuid, reason)
            return JsonResponse({
                "success": True,
                "action": "cancel",
                "message": "Your appointment has been cancelled successfully.",
                "details": result
            })
        
        else:
            return JsonResponse({
                "success": False,
                "error": f"Unknown action: {action}. Valid actions: list_types, book, list_events, cancel"
            }, status=400)
            
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


# ==================== CALENDLY WEBHOOK HANDLER ====================

@csrf_exempt
@require_http_methods(["POST"])
def calendly_webhook(request):
    """
    Webhook endpoint to receive Calendly booking notifications
    
    POST /api/calendly/webhook/
    
    Events:
        - invitee.created: Someone booked an appointment
        - invitee.canceled: Someone cancelled an appointment
    """
    try:
        data = json.loads(request.body)
        event_type = data.get('event')
        payload = data.get('payload', {})
        
        print(f"[Calendly Webhook] Received event: {event_type}")
        print(f"[Calendly Webhook] Full payload: {payload}")
        
        # Calendly webhook payload structure:
        # For invitee.created: payload contains 'email', 'name', 'scheduled_event' etc at top level
        # Also check nested 'invitee' object as fallback
        
        # Try top-level first (newer Calendly API format)
        invitee_name = payload.get('name') or payload.get('invitee', {}).get('name', 'Unknown')
        invitee_email = payload.get('email') or payload.get('invitee', {}).get('email', 'Unknown')
        
        # Get event info - check both formats
        scheduled_event = payload.get('scheduled_event', {})
        event_name = scheduled_event.get('name', 'Appointment')
        start_time = scheduled_event.get('start_time', '')
        
        # Format the time nicely
        formatted_time = start_time
        if start_time:
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                formatted_time = dt.strftime("%B %d, %Y at %I:%M %p")
            except:
                pass
        
        if event_type == 'invitee.created':
            # Someone booked an appointment
            message = f"🎉 *New Booking!*\n\n"
            message += f"👤 *Name:* {invitee_name}\n"
            message += f"📧 *Email:* {invitee_email}\n"
            message += f"📅 *Event:* {event_name}\n"
            message += f"🕐 *Time:* {formatted_time}\n"
            
            # Try to match booking to a CalendlyLink and process custom field + message
            try:
                from newapp.models import Admin, Organization, CalendlyLink, User, CustomField, CustomFieldValue
                import requests
                
                # Find matching CalendlyLink by URL
                event_uri = scheduled_event.get('event_type', '')
                scheduling_url = ''
                
                # Try to extract scheduling URL from the event type
                if event_uri:
                    # Calendly event_type URI format: https://api.calendly.com/event_types/UUID
                    service = get_service()
                    try:
                        headers_cal = {
                            'Authorization': f'Bearer {CALENDLY_ACCESS_TOKEN}',
                            'Content-Type': 'application/json'
                        }
                        et_resp = requests.get(event_uri, headers=headers_cal, timeout=10)
                        if et_resp.status_code == 200:
                            scheduling_url = et_resp.json().get('resource', {}).get('scheduling_url', '')
                    except:
                        pass
                
                # Find CalendlyLink matching this URL
                matched_link = None
                if scheduling_url:
                    matched_link = CalendlyLink.objects.filter(url__icontains=scheduling_url.split('/')[-1]).first()
                if not matched_link:
                    # Try matching by event name
                    matched_link = CalendlyLink.objects.filter(description__icontains=event_name).first()
                
                # If we found a matching link, process custom field + confirmation message
                if matched_link:
                    print(f"[Calendly Webhook] Matched CalendlyLink: {matched_link.name}")
                    
                    # Find the user by email or name
                    user_obj = None
                    if invitee_email and invitee_email != 'Unknown':
                        user_obj = User.objects.filter(email=invitee_email).first()
                    if not user_obj and invitee_name and invitee_name != 'Unknown':
                        user_obj = User.objects.filter(name__icontains=invitee_name).first()
                    
                    # Update custom field if configured
                    if matched_link.custom_field_name and user_obj:
                        try:
                            org = matched_link.organization
                            admin = matched_link.admin
                            cf = None
                            if org:
                                cf = CustomField.objects.filter(organization=org, name=matched_link.custom_field_name).first()
                            if not cf and admin:
                                cf = CustomField.objects.filter(admin=admin, name=matched_link.custom_field_name).first()
                            
                            if cf:
                                cfv, created = CustomFieldValue.objects.update_or_create(
                                    user=user_obj, custom_field=cf,
                                    defaults={'value': f'Booked - {event_name} on {formatted_time}'}
                                )
                                print(f"[Calendly Webhook] Updated custom field '{matched_link.custom_field_name}' for user {user_obj.phone_no}")
                        except Exception as cf_err:
                            print(f"[Calendly Webhook] Custom field error: {cf_err}")
                    
                    # Send custom confirmation message if configured
                    if matched_link.booking_message and user_obj and user_obj.phone_no:
                        try:
                            org = matched_link.organization
                            admin = matched_link.admin
                            phone_id = None
                            token = None
                            
                            if org:
                                phone_id = org.whatsapp_phone_id
                                token = org.whatsapp_token
                            elif admin:
                                phone_id = admin.whatsapp_phone_id
                                token = admin.whatsapp_token
                            
                            if phone_id and token:
                                # Replace placeholders in the message
                                confirm_msg = matched_link.booking_message
                                confirm_msg = confirm_msg.replace('{name}', invitee_name)
                                confirm_msg = confirm_msg.replace('{event}', event_name)
                                confirm_msg = confirm_msg.replace('{time}', formatted_time)
                                confirm_msg = confirm_msg.replace('{email}', invitee_email)
                                
                                whatsapp_url = f"https://graph.facebook.com/v17.0/{phone_id}/messages"
                                headers_wa = {
                                    "Authorization": f"Bearer {token}",
                                    "Content-Type": "application/json"
                                }
                                payload_wa = {
                                    "messaging_product": "whatsapp",
                                    "to": user_obj.phone_no,
                                    "type": "text",
                                    "text": {"body": confirm_msg}
                                }
                                r = requests.post(whatsapp_url, json=payload_wa, headers=headers_wa)
                                print(f"[Calendly Webhook] Sent confirmation to {user_obj.phone_no}: {r.status_code}")
                        except Exception as msg_err:
                            print(f"[Calendly Webhook] Confirmation message error: {msg_err}")
                
                # Notify admins about the booking
                admins_notified = []
                for admin in Admin.objects.exclude(whatsapp_phone_id='').exclude(whatsapp_token=''):
                    if admin.whatsapp_phone_id and admin.whatsapp_token and admin.display_phone_no:
                        notify_phone = admin.display_phone_no.replace(' ', '').replace('+', '')
                        whatsapp_url = f"https://graph.facebook.com/v17.0/{admin.whatsapp_phone_id}/messages"
                        headers_wa = {
                            "Authorization": f"Bearer {admin.whatsapp_token}",
                            "Content-Type": "application/json"
                        }
                        payload_wa = {
                            "messaging_product": "whatsapp",
                            "to": notify_phone,
                            "type": "text",
                            "text": {"body": message}
                        }
                        r = requests.post(whatsapp_url, json=payload_wa, headers=headers_wa)
                        admins_notified.append(admin.id)
            except Exception as wa_err:
                print(f"[Calendly Webhook] WhatsApp error: {wa_err}")
            
            return JsonResponse({"success": True, "event": "invitee.created"})
            
        elif event_type == 'invitee.canceled':
            message = f"❌ *Booking Cancelled*\n\n"
            message += f"👤 *Name:* {invitee_name}\n"
            message += f"📧 *Email:* {invitee_email}\n"
            
            try:
                from newapp.models import Admin
                import requests
                
                for admin in Admin.objects.exclude(whatsapp_phone_id='').exclude(whatsapp_token=''):
                    if admin.whatsapp_phone_id and admin.whatsapp_token and admin.display_phone_no:
                        admin_phone = admin.display_phone_no.replace(' ', '').replace('+', '')
                        whatsapp_url = f"https://graph.facebook.com/v17.0/{admin.whatsapp_phone_id}/messages"
                        headers = {
                            "Authorization": f"Bearer {admin.whatsapp_token}",
                            "Content-Type": "application/json"
                        }
                        payload_wa = {
                            "messaging_product": "whatsapp",
                            "to": admin_phone,
                            "type": "text",
                            "text": {"body": message}
                        }
                        requests.post(whatsapp_url, json=payload_wa, headers=headers)
            except Exception as wa_err:
                print(f"[Calendly Webhook] WhatsApp error: {wa_err}")
            
            return JsonResponse({"success": True, "event": "invitee.canceled"})
        
        return JsonResponse({"success": True, "message": "Event received"})
            
    except Exception as e:
        print(f"[Calendly Webhook] Error: {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)
