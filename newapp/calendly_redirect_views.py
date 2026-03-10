"""
Calendly Redirect Views - Booking detection without paid Calendly plan.

Flow:
1. AI sends {{calendly:link_name}} which becomes https://chatbotad.io/book/<TOKEN>
2. User clicks link -> this view redirects to actual Calendly URL
3. User books on Calendly -> Calendly redirects to /booking-confirmed/<TOKEN>/
4. This view identifies the user, updates custom field, sends WhatsApp confirmation
"""

import json
import requests
from django.http import HttpResponse, Http404
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from .models import CalendlyBookingTracker, CalendlyLink, User, CustomField, CustomFieldValue


@csrf_exempt
def book_redirect(request, token):
    """
    Step 1: User clicks the booking link.
    Looks up the tracker by token, marks as 'clicked', redirects to Calendly URL.
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

    # Redirect to the actual Calendly URL
    calendly_url = tracker.calendly_link.url
    return redirect(calendly_url)


@csrf_exempt
def booking_confirmed(request, token):
    """
    Step 2: Calendly redirects here after user books.
    Identifies the user, updates custom field, sends WhatsApp confirmation,
    and renders a thank-you page.
    """
    tracker = CalendlyBookingTracker.objects.filter(booking_token=token).select_related(
        'calendly_link', 'user'
    ).first()

    if not tracker:
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

    return render(request, 'booking_confirmed.html', {
        'success': True,
        'user_name': user.name or 'there',
        'link_name': link.description or link.name,
        'confirmation_sent': confirmation_sent,
        'custom_field_updated': custom_field_updated,
    })


def _send_whatsapp_confirmation(user, message, admin, org):
    """Send a WhatsApp message to confirm the booking."""
    from .models import Admin as AdminModel, Organization, Message
    from django.utils import timezone

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

    response = requests.post(url, headers=headers, json=payload, timeout=10)
    print(f"[CalendlyRedirect] WhatsApp API response {response.status_code}: {response.text[:200]}")

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
