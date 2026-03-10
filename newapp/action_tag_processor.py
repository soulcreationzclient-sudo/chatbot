
"""
Action Tag Processor for WhatsApp Messages

This module handles the processing of action tags in AI responses, 
allowing the chatbot to perform backend actions triggered by the prompt.

Supported Tags:
1. {{tag:add:tag_name}}    - Adds a tag to the user
2. {{tag:remove:tag_name}} - Removes a tag from the user
3. {{api:tool_name}}       - Executes a defined ExternalAPI tool

Usage in AI prompts:
    "I've marked you as a VIP. {{tag:add:vip}}"
    "Checking your invoice status... {{api:fetch_invoice}}"
    
The processor will:
1. Parse the tags from the response
2. Execute the corresponding actions (using logic.py)
3. Return the results and the cleaned text
"""

import re
import json
from . import logic

def parse_action_tags(text):
    """
    Extract all action tags from text.
    
    Returns:
        List of dicts: [{'type': 'tag_add', 'name': 'vip', 'full_tag': '{{tag:add:vip}}'}, ...]
    """
    actions = []
    
    # 1. Tag Add: {{tag:add:name}}
    tag_add_matches = re.finditer(r'\{\{tag:add:([a-zA-Z0-9_\-\s]+)\}\}', text)
    for match in tag_add_matches:
        actions.append({
            'type': 'tag_add',
            'name': match.group(1).strip(),
            'full_tag': match.group(0)
        })
        
    # 2. Tag Remove: {{tag:remove:name}}
    tag_remove_matches = re.finditer(r'\{\{tag:remove:([a-zA-Z0-9_\-\s]+)\}\}', text)
    for match in tag_remove_matches:
        actions.append({
            'type': 'tag_remove',
            'name': match.group(1).strip(),
            'full_tag': match.group(0)
        })
        
    # 3. API Call: {{api:name}} or {{api:name:key=val,key2=val2}}
    api_matches = re.finditer(r'\{\{api:([a-zA-Z0-9_]+)(?::([^}]+))?\}\}', text)
    for match in api_matches:
        params = {}
        if match.group(2):
            # Parse key=value pairs separated by commas
            for pair in match.group(2).split(','):
                pair = pair.strip()
                if '=' in pair:
                    k, v = pair.split('=', 1)
                    params[k.strip()] = v.strip()
        actions.append({
            'type': 'api_call',
            'name': match.group(1).strip(),
            'full_tag': match.group(0),
            'params': params
        })
    
    # 4. Calendly Link: {{calendly:name}}
    calendly_matches = re.finditer(r'\{\{calendly:([a-zA-Z0-9_\-\s]+)\}\}', text)
    for match in calendly_matches:
        actions.append({
            'type': 'calendly_link',
            'name': match.group(1).strip(),
            'full_tag': match.group(0)
        })
        
    return actions


def _replace_raw_calendly_urls(text, phone, admin, organization):
    """
    Safety filter: catch any raw calendly.com URLs the AI generated
    and replace them with our /book/<token>/ redirect URLs.
    """
    import re as _re
    import uuid
    calendly_pattern = _re.compile(r'https?://calendly\.com/[\w\-]+/[\w\-]+/?')
    matches = calendly_pattern.findall(text)
    if not matches:
        return text
    
    for raw_url in matches:
        try:
            from .models import CalendlyLink, CalendlyBookingTracker, User as UserModel
            # Try to find a matching CalendlyLink by URL
            link = None
            if organization:
                link = CalendlyLink.objects.filter(organization=organization).first()
            if not link and admin:
                link = CalendlyLink.objects.filter(admin=admin).first()
            
            if link:
                booking_token = uuid.uuid4().hex[:16]
                redirect_url = f"https://chatbotad.io/book/{booking_token}/"
                text = text.replace(raw_url, redirect_url)
                
                # Track the booking
                user_obj = UserModel.objects.filter(phone_no=phone).first()
                if user_obj:
                    CalendlyBookingTracker.objects.create(
                        user=user_obj,
                        calendly_link=link,
                        booking_token=booking_token,
                        status='link_sent'
                    )
                print(f"[ActionTag] SAFETY: Replaced raw Calendly URL with redirect: {redirect_url}")
            else:
                # No CalendlyLink found, just remove the raw URL
                text = text.replace(raw_url, '[booking link unavailable]')
                print(f"[ActionTag] SAFETY: Removed raw Calendly URL (no link configured)")
        except Exception as e:
            print(f"[ActionTag] SAFETY: Error replacing raw URL: {e}")
    
    return text


def process_response_actions(text, admin, phone, organization=None):
    """
    Process an AI response, extracting and executing action tags.
    
    Args:
        text (str): The full AI response text
        admin (Admin): The Admin model instance
        phone (str): User's phone number
        
    Returns:
        dict with:
            - 'original_text': str
            - 'final_text': str - Text with tags removed
            - 'actions_executed': list of results
            - 'api_responses': list of text responses from APIs (to be appended/sent)
    """
    result = {
        'original_text': text,
        'final_text': text,
        'actions_executed': [],
        'api_responses': []
    }
    
    # Set context for logic functions
    logic.set_current_context(phone, admin, organization)
    
    actions = parse_action_tags(text)
    
    if not actions:
        # Even without tags, check for raw Calendly URLs the AI might have generated
        result['final_text'] = _replace_raw_calendly_urls(text, phone, admin, organization)
        return result
        
    print(f"[ActionTag] Found {len(actions)} action(s) in response")
    
    # Sort actions by their position in text to process in order? 
    # Actually regex finditer yields in order.
    
    replacement_text = text
    
    for action in actions:
        tag = action['full_tag']
        action_type = action['type']
        name = action['name']
        outcome = ""
        
        # For calendly links, replace tag with redirect URL (token-based)
        # For other tags, remove the tag from text
        if action_type == 'calendly_link':
            # Look up the CalendlyLink record
            from .models import CalendlyLink
            link = None
            if organization:
                link = CalendlyLink.objects.filter(organization=organization, name__iexact=name).first()
            if not link and admin:
                link = CalendlyLink.objects.filter(admin=admin, name__iexact=name).first()
            
            if link:
                # Generate booking token and create redirect URL
                import uuid
                booking_token = uuid.uuid4().hex[:16]
                redirect_url = f"https://chatbotad.io/book/{booking_token}/"
                replacement_text = replacement_text.replace(tag, redirect_url)
                outcome = f"Calendly link '{name}' inserted as redirect: {redirect_url}"
                
                # Track this Calendly link send with booking token
                try:
                    from .models import CalendlyBookingTracker
                    from .models import User as UserModel
                    user_obj = UserModel.objects.filter(phone_no=phone).first()
                    if user_obj:
                        CalendlyBookingTracker.objects.create(
                            user=user_obj,
                            calendly_link=link,
                            booking_token=booking_token,
                            status='link_sent'
                        )
                        print(f"[ActionTag] Tracked Calendly link send: {phone} -> {link.name} (token: {booking_token})")
                except Exception as track_err:
                    print(f"[ActionTag] Tracking error (non-fatal): {track_err}")
                
                # Cancel any pending follow-ups for this user
                try:
                    from .models import ScheduledFollowUp, User as UserModel
                    user_obj = UserModel.objects.filter(phone_no=phone).first()
                    if user_obj:
                        cancelled = ScheduledFollowUp.objects.filter(
                            user=user_obj, status='pending'
                        ).update(status='cancelled')
                        if cancelled:
                            print(f"[ActionTag] Cancelled {cancelled} pending follow-ups for {phone} (Calendly link sent)")
                except Exception as fu_err:
                    print(f"[ActionTag] Follow-up cancel error (non-fatal): {fu_err}")
            else:
                replacement_text = replacement_text.replace(tag, "").strip()
                outcome = f"Warning: Calendly link '{name}' not found"
                print(f"[ActionTag] {outcome}")
        else:
            # Remove tag from text
            replacement_text = replacement_text.replace(tag, "").strip()
        
        try:
            if action_type == 'tag_add':
                outcome = logic.apply_user_tag(name, admin, phone)
                
            elif action_type == 'tag_remove':
                outcome = logic.remove_user_tag(name, admin, phone)
                
            elif action_type == 'api_call':
                # Execute API with context + any inline params
                context_args = {
                    "phone": phone,
                    "phone_no": phone
                }
                # Merge inline params from {{api:name:key=val}} format
                inline_params = action.get('params', {})
                if inline_params:
                    context_args.update(inline_params)
                
                api_response = logic.execute_tool(name, context_args, admin)
                
                outcome = f"API '{name}' executed."
                
                # Check if response looks like JSON or plain text
                try:
                    json_res = json.loads(api_response)
                    if isinstance(json_res, dict) and 'text' in json_res:
                         result['api_responses'].append(json_res['text'])
                    else:
                         result['api_responses'].append(str(json_res))
                         
                except ValueError:
                    result['api_responses'].append(api_response)
            
            elif action_type == 'calendly_link':
                pass  # Already handled above
                    
        except Exception as e:
            outcome = f"Error processing {tag}: {str(e)}"
            print(f"[ActionTag] {outcome}")
            
        result['actions_executed'].append({
            'tag': tag,
            'result': outcome
        })
        
    # Clean up whitespace
    replacement_text = re.sub(r'\n\s*\n', '\n\n', replacement_text).strip()
    # Safety filter: catch any remaining raw calendly.com URLs
    replacement_text = _replace_raw_calendly_urls(replacement_text, phone, admin, organization)
    result['final_text'] = replacement_text
    
    return result
