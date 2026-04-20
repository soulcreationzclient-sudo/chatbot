"""
Google Calendar Service
Provides calendar API integration for booking appointments.

Requires:
    pip install google-api-python-client google-auth

Usage:
    Once credentials are configured in GoogleCalendarLink.service_account_json,
    this service handles slot availability and event creation.
"""

import json
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def get_calendar_service(service_account_json):
    """
    Build Google Calendar API service from service account JSON credentials.

    Args:
        service_account_json: JSON string of service account credentials

    Returns:
        Google Calendar API service object, or None if credentials are missing
    """
    if not service_account_json:
        logger.error("No service account credentials provided")
        return None

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        creds_data = json.loads(service_account_json)
        credentials = service_account.Credentials.from_service_account_info(
            creds_data,
            scopes=['https://www.googleapis.com/auth/calendar']
        )
        service = build('calendar', 'v3', credentials=credentials)
        return service

    except ImportError:
        logger.error("google-api-python-client not installed. Run: pip install google-api-python-client google-auth")
        return None
    except Exception as e:
        logger.error(f"Failed to build Google Calendar service: {e}")
        return None


def get_available_slots(gcalendar_link, date_from=None, days_ahead=7):
    """
    Get available time slots for a GoogleCalendarLink.

    Args:
        gcalendar_link: GoogleCalendarLink model instance
        date_from: Start date (defaults to today)
        days_ahead: How many days ahead to check

    Returns:
        List of available slot dicts: [{"start": datetime, "end": datetime}, ...]
    """
    service = get_calendar_service(gcalendar_link.service_account_json)
    if not service:
        return []

    try:
        import pytz
        tz = pytz.timezone(gcalendar_link.timezone)
    except Exception:
        import pytz
        tz = pytz.UTC

    if not date_from:
        # Use localize() to get the correct UTC offset for midnight (avoids DST issues)
        today = datetime.now(tz).date()
        date_from = tz.localize(datetime(today.year, today.month, today.day, 0, 0, 0))

    date_to = date_from + timedelta(days=days_ahead)

    try:
        # Get existing events (busy times)
        events_result = service.events().list(
            calendarId=gcalendar_link.calendar_id,
            timeMin=date_from.isoformat(),
            timeMax=date_to.isoformat(),
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        busy_times = []
        for event in events_result.get('items', []):
            start = event.get('start', {}).get('dateTime')
            end = event.get('end', {}).get('dateTime')
            if start and end:
                busy_times.append({
                    'start': datetime.fromisoformat(start),
                    'end': datetime.fromisoformat(end)
                })

        # Generate possible slots
        available_slots = []
        duration = timedelta(minutes=gcalendar_link.duration_minutes)
        available_days = gcalendar_link.available_days or list(range(7))

        current = date_from
        while current < date_to:
            # Check if day is available (0=Monday...6=Sunday)
            if current.weekday() in available_days:
                # Generate slots for this day
                slot_start = current.replace(
                    hour=gcalendar_link.start_hour, minute=0, second=0, microsecond=0
                )
                day_end = current.replace(
                    hour=gcalendar_link.end_hour, minute=0, second=0, microsecond=0
                )

                while slot_start + duration <= day_end:
                    slot_end = slot_start + duration

                    # Check if this slot conflicts with any busy time
                    is_free = True
                    for busy in busy_times:
                        if slot_start < busy['end'] and slot_end > busy['start']:
                            is_free = False
                            break

                    # Only include future slots
                    if is_free and slot_start > datetime.now(tz):
                        available_slots.append({
                            'start': slot_start,
                            'end': slot_end
                        })

                    slot_start += duration  # Move to next slot

            current += timedelta(days=1)

        return available_slots

    except Exception as e:
        logger.error(f"Failed to get available slots: {e}")
        return []


def create_event(gcalendar_link, slot_start, attendee_name='', attendee_email=''):
    """
    Create a Google Calendar event for a confirmed booking.

    Args:
        gcalendar_link: GoogleCalendarLink model instance
        slot_start: datetime of the appointment start
        attendee_name: Name of the attendee
        attendee_email: Email of the attendee

    Returns:
        dict with event_id and link, or error
    """
    service = get_calendar_service(gcalendar_link.service_account_json)
    if not service:
        return {'success': False, 'error': 'Calendar service not available'}

    slot_end = slot_start + timedelta(minutes=gcalendar_link.duration_minutes)

    event_body = {
        'summary': f'{gcalendar_link.description or gcalendar_link.name} - {attendee_name}',
        'start': {'dateTime': slot_start.isoformat(), 'timeZone': gcalendar_link.timezone},
        'end': {'dateTime': slot_end.isoformat(), 'timeZone': gcalendar_link.timezone},
    }

    if attendee_email:
        event_body['attendees'] = [{'email': attendee_email}]

    try:
        event = service.events().insert(
            calendarId=gcalendar_link.calendar_id,
            body=event_body,
            sendUpdates='all' if attendee_email else 'none'
        ).execute()

        logger.info(f"Created Google Calendar event: {event.get('id')}")
        return {
            'success': True,
            'event_id': event.get('id'),
            'html_link': event.get('htmlLink'),
        }

    except Exception as e:
        logger.error(f"Failed to create event: {e}")
        return {'success': False, 'error': str(e)}


def cancel_event(gcalendar_link, event_id):
    """Cancel/delete a Google Calendar event."""
    service = get_calendar_service(gcalendar_link.service_account_json)
    if not service:
        return {'success': False, 'error': 'Calendar service not available'}

    try:
        service.events().delete(
            calendarId=gcalendar_link.calendar_id,
            eventId=event_id,
            sendUpdates='all'
        ).execute()
        logger.info(f"Cancelled event {event_id}")
        return {'success': True}
    except Exception as e:
        logger.error(f"Failed to cancel event: {e}")
        return {'success': False, 'error': str(e)}
