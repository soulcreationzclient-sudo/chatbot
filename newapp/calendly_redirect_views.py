"""
Calendly Redirect Views - Booking detection without paid Calendly plan.

Flow (Embed approach - works on FREE plan):
1. AI sends {{calendly:link_name}} which becomes https://chatbotad.io/book/<TOKEN>
2. User clicks link -> sees Calendly embedded on OUR page
3. User books -> Calendly JS widget fires 'calendly.event_scheduled' event
4. Our JavaScript catches it -> sends AJAX to /booking-confirmed/<TOKEN>/
5. Server identifies the user, updates custom field, sends WhatsApp confirmation
"""

import json
import requests
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from .models import CalendlyBookingTracker, CalendlyLink, User, CustomField, CustomFieldValue


@csrf_exempt
def book_redirect(request, token):
    """
    Renders a page with Calendly embedded inline.
    When user completes booking, JS fires an event that triggers confirmation.
    """
    tracker = CalendlyBookingTracker.objects.filter(booking_token=token).select_related('calendly_link').first()
    if not tracker:
        return HttpResponse(
            "<h2>Booking link not found or expired.</h2>"
            "<p>Please request a new booking link from the chat.</p>",
            status=404
        )

    # Mark as clicked
    tracker.status = 'clicked'
    tracker.save(update_fields=['status', 'updated_at'])

    # Render our page with embedded Calendly widget
    return render(request, 'calendly_embed.html', {
        'calendly_url': tracker.calendly_link.url,
        'booking_token': token,
        'link_name': tracker.calendly_link.description or tracker.calendly_link.name,
    })


@csrf_exempt
def booking_confirmed(request, token=None):
    """
    Called via AJAX when Calendly booking is completed.
    Also accessible directly as a fallback.
    Identifies the user, updates custom field, sends WhatsApp confirmation.
    """
    # Handle both AJAX POST and direct GET
    if not token or token == 'done':
        # Try from cookie or POST data
        token = request.COOKIES.get('booking_token')
        if not token and request.method == 'POST':
            try:
                body = json.loads(request.body)
                token = body.get('token')
            except:
                pass

    if not token:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.content_type == 'application/json':
            return JsonResponse({'success': False, 'message': 'No booking token found'}, status=400)
        return render(request, 'booking_confirmed.html', {
            'success': False,
            'message': 'Could not identify your booking. Please check your WhatsApp for confirmation.'
        })

    tracker = CalendlyBookingTracker.objects.filter(booking_token=token).select_related(
        'calendly_link', 'user'
    ).first()

    if not tracker:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.content_type == 'application/json':
            return JsonResponse({'success': False, 'message': 'Booking token not found'}, status=404)
        return render(request, 'booking_confirmed.html', {
            'success': False,
            'message': 'Booking link not found or expired.'
        })

    # Check if already processed to avoid duplicate messages
    already_processed = tracker.status == 'booked'

    # Mark as booked
    tracker.status = 'booked'
    tracker.save(update_fields=['status', 'updated_at'])

    user = tracker.user
    link = tracker.calendly_link
    org = user.organization
    admin = user.admin_id

    # Update custom field if configured on the CalendlyLink
    custom_field_updated = False
    if link.custom_field_name:
        try:
            cf = None
            if org:
                cf = CustomField.objects.filter(organization=org, name=link.custom_field_name, is_active=True).first()
            elif admin:
                cf = CustomField.objects.filter(admin=admin, name=link.custom_field_name, is_active=True).first()

            if cf:
                CustomFieldValue.objects.update_or_create(
                    custom_field=cf,
                    user=user,
                    defaults={'value': 'Booked'}
                )
                custom_field_updated = True
                print(f"[CalendlyRedirect] Updated custom field '{link.custom_field_name}' to 'Booked' for {user.phone_no}")
                
                # Trigger pipeline automation for custom field change
                try:
                    from .controllers.pipeline import run_pipeline_automations
                    run_pipeline_automations(
                        user.id,
                        'custom_field_changed',
                        field_name=link.custom_field_name,
                        field_value='Booked'
                    )
                    print(f"[CalendlyRedirect] Pipeline automation triggered for {user.phone_no}")
                except Exception as auto_err:
                    print(f"[CalendlyRedirect] Pipeline automation error (non-fatal): {auto_err}")
        except Exception as e:
            print(f"[CalendlyRedirect] Error updating custom field: {e}")

    # Send WhatsApp confirmation message (only if not already processed)
    confirmation_sent = False
    if not already_processed and link.booking_message:
        try:
            _send_whatsapp_confirmation(user, link.booking_message, admin, org)
            confirmation_sent = True
            print(f"[CalendlyRedirect] Sent WhatsApp confirmation to {user.phone_no}")
        except Exception as e:
            print(f"[CalendlyRedirect] Error sending WhatsApp confirmation: {e}")

    # Return JSON for AJAX requests, HTML for direct access
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.content_type == 'application/json':
        return JsonResponse({
            'success': True,
            'confirmation_sent': confirmation_sent,
            'custom_field_updated': custom_field_updated,
            'user_name': user.name or 'there',
        })

    return render(request, 'booking_confirmed.html', {
        'success': True,
        'user_name': user.name or 'there',
        'link_name': link.description or link.name,
        'confirmation_sent': confirmation_sent,
        'custom_field_updated': custom_field_updated,
    })


def _send_whatsapp_confirmation(user, message, admin, org):
    """Send a WhatsApp or Webchat message to confirm the booking."""
    from .models import Admin as AdminModel, Organization, Message, WebChatSession, WebChatMessage
    from django.utils import timezone

    if user.phone_no and user.phone_no.startswith('webchat_'):
        try:
            session = WebChatSession.objects.filter(user=user).order_by('-last_activity').first()
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
                print(f"[CalendlyRedirect] Sent webchat confirmation to {user.phone_no}")
            else:
                print(f"[CalendlyRedirect] No active webchat session found for {user.phone_no}")
        except Exception as e:
            print(f"[CalendlyRedirect] Error sending webchat confirmation: {e}")
        return

    # Get WhatsApp credentials
    phone_id = None
    token = None

    if org:
        phone_id = org.whatsapp_phone_id
        token = org.whatsapp_token
    elif admin:
        phone_id = admin.whatsapp_phone_id
        token = admin.whatsapp_token

    if not phone_id or not token:
        print(f"[CalendlyRedirect] No WhatsApp credentials found for user {user.phone_no}")
        return

    # Send via WhatsApp API
    url = f"https://graph.facebook.com/v18.0/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": user.phone_no,
        "type": "text",
        "text": {"body": message}
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        print(f"[CalendlyRedirect] WhatsApp API response {response.status_code}: {response.text[:200]}")
    except Exception as e:
        print(f"[CalendlyRedirect] Error calling WhatsApp API: {e}")

    # Save message to conversation history
    try:
        Message.objects.create(
            user_id=user,
            messages=message,
            created_at=timezone.now(),
            who='bot'
        )
    except Exception as e:
        print(f"[CalendlyRedirect] Error saving message: {e}")
