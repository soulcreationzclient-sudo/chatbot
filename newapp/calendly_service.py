"""
Calendly API Service Module
Handles booking and cancellation of appointments via Calendly API v2
"""

import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
import os

class CalendlyService:
    """Service class for Calendly API integration"""
    
    BASE_URL = "https://api.calendly.com"
    
    def __init__(self, access_token: str = None):
        """
        Initialize Calendly service with access token
        
        Args:
            access_token: Calendly Personal Access Token. 
                         If not provided, reads from CALENDLY_ACCESS_TOKEN env var
        """
        self.access_token = access_token or os.environ.get('CALENDLY_ACCESS_TOKEN')
        if not self.access_token:
            raise ValueError("Calendly access token is required")
        
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        self._user_uri = None
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """Make HTTP request to Calendly API"""
        url = f"{self.BASE_URL}{endpoint}"
        response = requests.request(method, url, headers=self.headers, **kwargs)
        
        if response.status_code >= 400:
            error_msg = response.json().get('message', response.text)
            raise Exception(f"Calendly API Error ({response.status_code}): {error_msg}")
        
        return response.json() if response.text else {}
    
    def get_current_user(self) -> Dict:
        """Get current authenticated user info"""
        result = self._make_request("GET", "/users/me")
        self._user_uri = result.get('resource', {}).get('uri')
        return result.get('resource', {})
    
    @property
    def user_uri(self) -> str:
        """Get user URI, fetching if not cached"""
        if not self._user_uri:
            self.get_current_user()
        return self._user_uri
    
    # ==================== BOOKING FUNCTIONS ====================
    
    def get_event_types(self, active_only: bool = True) -> List[Dict]:
        """
        Get all event types for the current user
        
        Args:
            active_only: If True, only return active event types
            
        Returns:
            List of event type objects
        """
        params = {"user": self.user_uri}
        if active_only:
            params["active"] = "true"
        
        result = self._make_request("GET", "/event_types", params=params)
        return result.get('collection', [])
    
    def get_available_times(
        self, 
        event_type_uri: str, 
        start_time: datetime = None,
        end_time: datetime = None
    ) -> List[Dict]:
        """
        Get available time slots for an event type
        
        Args:
            event_type_uri: URI of the event type
            start_time: Start of time range (default: now)
            end_time: End of time range (default: 7 days from now)
            
        Returns:
            List of available time slots
        """
        if not start_time:
            start_time = datetime.utcnow()
        if not end_time:
            end_time = start_time + timedelta(days=7)
        
        params = {
            "event_type": event_type_uri,
            "start_time": start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end_time": end_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        }
        
        result = self._make_request("GET", "/event_type_available_times", params=params)
        return result.get('collection', [])
    
    def create_booking(
        self,
        event_type_uri: str,
        start_time: str,
        invitee_email: str,
        invitee_name: str,
        timezone: str = "Asia/Kolkata",
        questions_and_answers: List[Dict] = None
    ) -> Dict:
        """
        Book an appointment (create invitee)
        
        Args:
            event_type_uri: URI of the event type to book
            start_time: Start time in ISO format (UTC)
            invitee_email: Email of the person booking
            invitee_name: Name of the person booking
            timezone: Timezone of the invitee
            questions_and_answers: Optional custom questions/answers
            
        Returns:
            Booking confirmation details
        """
        # First, we need to get the scheduling link for this event type
        event_types = self.get_event_types()
        event_type = next((et for et in event_types if et.get('uri') == event_type_uri), None)
        
        if not event_type:
            raise ValueError(f"Event type not found: {event_type_uri}")
        
        scheduling_url = event_type.get('scheduling_url')
        
        # For creating bookings programmatically, we use the scheduling API
        # This requires the event type UUID
        event_type_uuid = event_type_uri.split('/')[-1]
        
        payload = {
            "event_type_uuid": event_type_uuid,
            "start_time": start_time,
            "invitee": {
                "email": invitee_email,
                "name": invitee_name,
                "timezone": timezone
            }
        }
        
        if questions_and_answers:
            payload["questions_and_answers"] = questions_and_answers
        
        # Note: The create invitee endpoint requires specific API access
        # Using the one-off scheduling endpoint
        result = self._make_request(
            "POST", 
            f"/scheduling_links",
            json={
                "max_event_count": 1,
                "owner": event_type_uri,
                "owner_type": "EventType"
            }
        )
        
        return {
            "booking_url": result.get('resource', {}).get('booking_url'),
            "event_type": event_type.get('name'),
            "message": "Please use this link to complete your booking"
        }
    
    # ==================== CANCELLATION FUNCTIONS ====================
    
    def get_scheduled_events(
        self,
        invitee_email: str = None,
        status: str = "active",
        min_start_time: datetime = None,
        max_start_time: datetime = None
    ) -> List[Dict]:
        """
        Get scheduled events (appointments)
        
        Args:
            invitee_email: Filter by invitee email
            status: Filter by status ('active', 'canceled')
            min_start_time: Minimum start time filter
            max_start_time: Maximum start time filter
            
        Returns:
            List of scheduled events
        """
        params = {
            "user": self.user_uri,
            "status": status
        }
        
        if invitee_email:
            params["invitee_email"] = invitee_email
        if min_start_time:
            params["min_start_time"] = min_start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        if max_start_time:
            params["max_start_time"] = max_start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        result = self._make_request("GET", "/scheduled_events", params=params)
        return result.get('collection', [])
    
    def get_event_invitees(self, event_uuid: str) -> List[Dict]:
        """Get invitees for a specific event"""
        result = self._make_request("GET", f"/scheduled_events/{event_uuid}/invitees")
        return result.get('collection', [])
    
    def cancel_event(self, event_uuid: str, reason: str = "Cancelled via chatbot") -> Dict:
        """
        Cancel a scheduled event
        
        Args:
            event_uuid: UUID of the event to cancel
            reason: Reason for cancellation
            
        Returns:
            Cancellation confirmation
        """
        payload = {"reason": reason}
        
        result = self._make_request(
            "POST",
            f"/scheduled_events/{event_uuid}/cancellation",
            json=payload
        )
        
        return {
            "status": "cancelled",
            "message": f"Event has been cancelled. Reason: {reason}",
            "details": result
        }
    
    # ==================== UTILITY FUNCTIONS ====================
    
    def format_available_times(self, available_times: List[Dict]) -> List[str]:
        """Format available times for display"""
        formatted = []
        for slot in available_times:
            start = datetime.fromisoformat(slot['start_time'].replace('Z', '+00:00'))
            formatted.append(start.strftime("%A, %B %d at %I:%M %p"))
        return formatted
    
    def format_scheduled_events(self, events: List[Dict]) -> List[Dict]:
        """Format scheduled events for display"""
        formatted = []
        for event in events:
            start = datetime.fromisoformat(event['start_time'].replace('Z', '+00:00'))
            formatted.append({
                "uuid": event['uri'].split('/')[-1],
                "name": event.get('name', 'Appointment'),
                "start_time": start.strftime("%A, %B %d at %I:%M %p"),
                "status": event.get('status'),
                "cancel_url": event.get('cancel_url'),
                "reschedule_url": event.get('reschedule_url')
            })
        return formatted


# ==================== DJANGO VIEW HELPER FUNCTIONS ====================

def get_calendly_service() -> CalendlyService:
    """Get Calendly service instance with token from settings"""
    from django.conf import settings
    token = getattr(settings, 'CALENDLY_ACCESS_TOKEN', None) or os.environ.get('CALENDLY_ACCESS_TOKEN')
    return CalendlyService(access_token=token)
