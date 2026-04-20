"""
Google Calendar Booking Views
Public endpoints for the booking page flow.

Flow:
1. AI sends {{gcalendar:consultation}} -> /gcalendar/book/<token>/
2. User clicks link -> sees available slots
3. User picks slot -> POST confirms booking
"""

import json
from datetime import datetime
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods


def gcalendar_booking_page(request, token):
    """
    Public booking page — shows available time slots.
    """
    from newapp.models import GoogleCalendarBooking, GoogleCalendarLink

    booking = get_object_or_404(GoogleCalendarBooking, booking_token=token)
    gcal_link = booking.gcalendar_link

    if not gcal_link.is_active:
        raise Http404("This booking link is no longer active.")

    # Get available slots
    from newapp.gcalendar_service import get_available_slots
    slots = get_available_slots(gcal_link)

    # Group slots by day for display
    slots_by_day = {}
    for slot in slots[:30]:  # Limit to 30 slots
        day_key = slot['start'].strftime('%A, %B %d')
        if day_key not in slots_by_day:
            slots_by_day[day_key] = []
        slots_by_day[day_key].append({
            'start': slot['start'].isoformat(),
            'end': slot['end'].isoformat(),
            'display': slot['start'].strftime('%I:%M %p') + ' — ' + slot['end'].strftime('%I:%M %p'),
        })

    context = {
        'booking': booking,
        'gcal_link': gcal_link,
        'slots_by_day': slots_by_day,
        'slots_json': json.dumps({k: v for k, v in slots_by_day.items()}),
        'token': token,
    }
    return render(request, 'gcalendar/booking.html', context)


@csrf_exempt
@require_http_methods(["POST"])
def gcalendar_confirm_booking(request, token):
    """
    Confirm a booking — creates Google Calendar event.
    """
    from newapp.models import GoogleCalendarBooking
    from newapp.gcalendar_service import create_event

    booking = get_object_or_404(GoogleCalendarBooking, booking_token=token)

    if booking.status == 'booked':
        return JsonResponse({'error': 'This slot is already booked'}, status=400)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid request'}, status=400)

    slot_start_str = data.get('slot_start')
    name = data.get('name', '').strip()
    email = data.get('email', '').strip()

    if not slot_start_str:
        return JsonResponse({'error': 'Please select a time slot'}, status=400)

    try:
        slot_start = datetime.fromisoformat(slot_start_str)
    except ValueError:
        return JsonResponse({'error': 'Invalid date format'}, status=400)

    # Create Google Calendar event
    result = create_event(
        booking.gcalendar_link,
        slot_start,
        attendee_name=name or (booking.user.name if booking.user else ''),
        attendee_email=email
    )

    if result.get('success'):
        booking.status = 'booked'
        booking.selected_slot = slot_start
        booking.google_event_id = result.get('event_id', '')
        booking.attendee_name = name
        booking.attendee_email = email
        booking.save()

        # Update custom field if configured
        if booking.gcalendar_link.custom_field_name and booking.user:
            try:
                from newapp.models import CustomFieldValue, CustomField
                field = CustomField.objects.filter(
                    name=booking.gcalendar_link.custom_field_name
                ).first()
                if field:
                    CustomFieldValue.objects.update_or_create(
                        user=booking.user, custom_field=field,
                        defaults={'value': f'booked:{slot_start.strftime("%Y-%m-%d %H:%M")}'}
                    )
            except Exception:
                pass

        # Send confirmation via WhatsApp or Webchat if booking_message is set
        if booking.gcalendar_link.booking_message and booking.user:
            try:
                message = booking.gcalendar_link.booking_message.replace(
                    '{date}', slot_start.strftime('%B %d, %Y')
                ).replace('{time}', slot_start.strftime('%I:%M %p'))

                if booking.user.phone_no and booking.user.phone_no.startswith('webchat_'):
                    from newapp.models import WebChatSession, WebChatMessage
                    from django.utils import timezone
                    
                    session = WebChatSession.objects.filter(user=booking.user).order_by('-last_activity').first()
                    if session:
                        WebChatMessage.objects.create(
                            session=session,
                            content=message,
                            sender='bot',
                            content_type='text'
                        )
                        session.last_activity = timezone.now()
                        session.message_count += 1
                        session.save(update_fields=['last_activity', 'message_count'])
                else:
                    from newapp.models import Organization
                    org = booking.gcalendar_link.organization
                    if org and org.whatsapp_phone_id and org.whatsapp_token:
                        import requests as req

                        req.post(
                            f"https://graph.facebook.com/v22.0/{org.whatsapp_phone_id}/messages",
                            headers={
                                "Authorization": f"Bearer {org.whatsapp_token}",
                                "Content-Type": "application/json"
                            },
                            json={
                                "messaging_product": "whatsapp",
                                "to": booking.user.phone_no,
                                "type": "text",
                                "text": {"body": message}
                            },
                            timeout=10
                        )
            except Exception:
                pass  # Don't fail booking if message send fails

        return JsonResponse({
            'success': True,
            'message': 'Booking confirmed!',
            'event_link': result.get('html_link', '')
        })
    else:
        return JsonResponse({
            'success': False,
            'error': result.get('error', 'Failed to create calendar event. Please try again.')
        }, status=500)
