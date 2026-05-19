"""
Unified Channel Message Sender for SpeedBot

Routes messages to the correct platform API based on the user's channel.
Supports: WhatsApp, Instagram DM, Facebook Messenger

Usage:
    from newapp.channel_sender import send_channel_message, send_interactive_buttons
    
    # Send a plain text message to any channel
    send_channel_message(user, "Hello!", organization)
    
    # Send WhatsApp interactive buttons
    send_interactive_buttons(phone, button_group_data, phone_id, token)
"""

import requests
import json
import logging

logger = logging.getLogger('channel_sender')


# ==================== WHATSAPP ====================

def send_whatsapp_text(phone, text, phone_id, token):
    """Send a plain text message via WhatsApp Cloud API."""
    url = f"https://graph.facebook.com/v21.0/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {"body": text}
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=20)
        data = res.json()
        if res.status_code == 200 and "messages" in data:
            logger.info(f"[WA] Sent text to {phone}: {text[:50]}...")
            return {'success': True, 'data': data}
        else:
            err = (data.get("error") or {}).get("message", str(data))
            logger.error(f"[WA] Failed to send to {phone}: {err}")
            return {'success': False, 'error': err}
    except Exception as e:
        logger.error(f"[WA] Exception sending to {phone}: {e}")
        return {'success': False, 'error': str(e)}


def send_interactive_buttons(phone, button_group, phone_id, token, text_before=None):
    """
    Send a WhatsApp interactive button message.
    
    Args:
        phone: Recipient phone number
        button_group: Dict with keys: header_text, body_text, footer_text, buttons[]
            Each button: {id, title, type, payload}
        phone_id: WhatsApp Phone Number ID
        token: WhatsApp API token
        text_before: Optional text message to send BEFORE the buttons (the AI's text response)
    
    Returns:
        dict with success/error
    """
    url = f"https://graph.facebook.com/v21.0/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # If there's text before the buttons, send it as a separate message first
    if text_before and text_before.strip():
        send_whatsapp_text(phone, text_before, phone_id, token)
    
    # Separate reply buttons from URL buttons
    reply_buttons = [b for b in button_group.get('buttons', []) if b.get('type') == 'reply']
    url_buttons = [b for b in button_group.get('buttons', []) if b.get('type') == 'url']
    
    results = []
    
    # Send reply buttons as interactive message (max 3)
    if reply_buttons:
        interactive = {
            "type": "button",
            "body": {"text": button_group.get('body_text', 'Please choose an option:')},
            "action": {
                "buttons": [
                    {
                        "type": "reply",
                        "reply": {
                            "id": btn['id'],
                            "title": btn['title'][:20]
                        }
                    }
                    for btn in reply_buttons[:3]  # WhatsApp max 3 buttons
                ]
            }
        }
        
        # Add optional header
        if button_group.get('header_text'):
            interactive["header"] = {"type": "text", "text": button_group['header_text'][:60]}
        
        # Add optional footer
        if button_group.get('footer_text'):
            interactive["footer"] = {"text": button_group['footer_text'][:60]}
        
        payload = {
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "interactive",
            "interactive": interactive
        }
        
        try:
            res = requests.post(url, json=payload, headers=headers, timeout=20)
            data = res.json()
            if res.status_code == 200 and "messages" in data:
                logger.info(f"[WA] Sent interactive buttons to {phone}: {[b['title'] for b in reply_buttons[:3]]}")
                results.append({'success': True, 'type': 'interactive', 'data': data})
            else:
                err = (data.get("error") or {}).get("message", str(data))
                logger.error(f"[WA] Failed to send buttons to {phone}: {err}")
                results.append({'success': False, 'type': 'interactive', 'error': err})
        except Exception as e:
            logger.error(f"[WA] Exception sending buttons to {phone}: {e}")
            results.append({'success': False, 'type': 'interactive', 'error': str(e)})
    
    # Send URL buttons as separate text messages with links (WhatsApp interactive doesn't support URL buttons natively)
    for btn in url_buttons:
        link_msg = f"🔗 {btn['title']}: {btn['payload']}"
        res = send_whatsapp_text(phone, link_msg, phone_id, token)
        results.append({'success': res.get('success', False), 'type': 'url', 'data': res})
    
    return results


# ==================== INSTAGRAM ====================

def send_instagram_text(igsid, text, page_token):
    """
    Send a text message via Instagram DM API.
    
    Args:
        igsid: Instagram-Scoped User ID
        text: Message text
        page_token: Facebook Page Access Token (with instagram_manage_messages permission)
    """
    url = "https://graph.facebook.com/v21.0/me/messages"
    headers = {
        "Authorization": f"Bearer {page_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "recipient": {"id": igsid},
        "message": {"text": text}
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=20)
        data = res.json()
        if res.status_code == 200:
            logger.info(f"[IG] Sent text to {igsid}: {text[:50]}...")
            return {'success': True, 'data': data}
        else:
            err = data.get("error", {}).get("message", str(data))
            logger.error(f"[IG] Failed to send to {igsid}: {err}")
            return {'success': False, 'error': err}
    except Exception as e:
        logger.error(f"[IG] Exception sending to {igsid}: {e}")
        return {'success': False, 'error': str(e)}


def send_instagram_quick_replies(igsid, text, quick_replies, page_token):
    """
    Send a message with quick replies via Instagram DM API.
    Instagram supports up to 13 quick replies per message.
    
    Args:
        igsid: Instagram-Scoped User ID
        text: Message text
        quick_replies: List of dicts with {title, payload}
        page_token: Facebook Page Access Token
    """
    url = "https://graph.facebook.com/v21.0/me/messages"
    headers = {
        "Authorization": f"Bearer {page_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "recipient": {"id": igsid},
        "message": {
            "text": text,
            "quick_replies": [
                {
                    "content_type": "text",
                    "title": qr['title'][:20],
                    "payload": qr.get('payload', qr['title'])
                }
                for qr in quick_replies[:13]
            ]
        }
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=20)
        data = res.json()
        if res.status_code == 200:
            logger.info(f"[IG] Sent quick replies to {igsid}")
            return {'success': True, 'data': data}
        else:
            err = data.get("error", {}).get("message", str(data))
            logger.error(f"[IG] Failed quick replies to {igsid}: {err}")
            return {'success': False, 'error': err}
    except Exception as e:
        logger.error(f"[IG] Exception sending quick replies to {igsid}: {e}")
        return {'success': False, 'error': str(e)}


# ==================== FACEBOOK MESSENGER ====================

def send_facebook_text(psid, text, page_token):
    """
    Send a text message via Facebook Messenger Send API.
    
    Args:
        psid: Page-Scoped User ID
        text: Message text
        page_token: Facebook Page Access Token
    """
    url = "https://graph.facebook.com/v21.0/me/messages"
    headers = {
        "Authorization": f"Bearer {page_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "recipient": {"id": psid},
        "message": {"text": text}
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=20)
        data = res.json()
        if res.status_code == 200:
            logger.info(f"[FB] Sent text to {psid}: {text[:50]}...")
            return {'success': True, 'data': data}
        else:
            err = data.get("error", {}).get("message", str(data))
            logger.error(f"[FB] Failed to send to {psid}: {err}")
            return {'success': False, 'error': err}
    except Exception as e:
        logger.error(f"[FB] Exception sending to {psid}: {e}")
        return {'success': False, 'error': str(e)}


def send_facebook_quick_replies(psid, text, quick_replies, page_token):
    """
    Send a message with quick replies via Facebook Messenger.
    Messenger supports up to 13 quick replies.
    
    Args:
        psid: Page-Scoped User ID
        text: Message text
        quick_replies: List of dicts with {title, payload}
        page_token: Facebook Page Access Token
    """
    url = "https://graph.facebook.com/v21.0/me/messages"
    headers = {
        "Authorization": f"Bearer {page_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "recipient": {"id": psid},
        "message": {
            "text": text,
            "quick_replies": [
                {
                    "content_type": "text",
                    "title": qr['title'][:20],
                    "payload": qr.get('payload', qr['title'])
                }
                for qr in quick_replies[:13]
            ]
        }
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=20)
        data = res.json()
        if res.status_code == 200:
            logger.info(f"[FB] Sent quick replies to {psid}")
            return {'success': True, 'data': data}
        else:
            err = data.get("error", {}).get("message", str(data))
            logger.error(f"[FB] Failed quick replies to {psid}: {err}")
            return {'success': False, 'error': err}
    except Exception as e:
        logger.error(f"[FB] Exception sending quick replies to {psid}: {e}")
        return {'success': False, 'error': str(e)}


def send_facebook_typing(psid, page_token, action='typing_on'):
    """Send typing indicator via Facebook Messenger."""
    url = "https://graph.facebook.com/v21.0/me/messages"
    headers = {
        "Authorization": f"Bearer {page_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "recipient": {"id": psid},
        "sender_action": action  # typing_on, typing_off, mark_seen
    }
    try:
        requests.post(url, json=payload, headers=headers, timeout=10)
    except Exception:
        pass  # Non-critical, ignore errors


# ==================== UNIFIED ROUTER ====================

def send_channel_message(user, message_text, organization, buttons=None):
    """
    Send a message to a user via their channel (WhatsApp/Instagram/Facebook).
    
    Args:
        user: User model instance (has phone_no and source fields)
        message_text: Text to send
        organization: Organization model instance (has credentials)
        buttons: Optional button_group data dict for interactive messages
    
    Returns:
        dict with success/error
    """
    channel = (user.source or 'Whatsapp').lower()
    
    if channel in ('whatsapp', 'wa'):
        phone_id = organization.whatsapp_phone_id
        token = organization.whatsapp_token
        
        if not phone_id or not token:
            return {'success': False, 'error': 'WhatsApp not configured'}
        
        if buttons:
            return send_interactive_buttons(
                user.phone_no, buttons, phone_id, token, text_before=message_text
            )
        return send_whatsapp_text(user.phone_no, message_text, phone_id, token)
    
    elif channel in ('instagram', 'ig'):
        page_token = organization.instagram_token
        if not page_token:
            return {'success': False, 'error': 'Instagram not configured'}
        
        # For Instagram, phone_no stores the IGSID
        if buttons:
            # Convert buttons to Instagram quick replies
            quick_replies = [
                {'title': b['title'], 'payload': b.get('payload', b['title'])}
                for b in buttons.get('buttons', [])
                if b.get('type') == 'reply'
            ]
            if quick_replies:
                return send_instagram_quick_replies(
                    user.phone_no, message_text, quick_replies, page_token
                )
        return send_instagram_text(user.phone_no, message_text, page_token)
    
    elif channel in ('facebook', 'fb', 'messenger'):
        page_token = organization.facebook_token
        if not page_token:
            return {'success': False, 'error': 'Facebook not configured'}
        
        # For Facebook, phone_no stores the PSID
        if buttons:
            quick_replies = [
                {'title': b['title'], 'payload': b.get('payload', b['title'])}
                for b in buttons.get('buttons', [])
                if b.get('type') == 'reply'
            ]
            if quick_replies:
                return send_facebook_quick_replies(
                    user.phone_no, message_text, quick_replies, page_token
                )
        return send_facebook_text(user.phone_no, message_text, page_token)
    
    else:
        logger.warning(f"Unknown channel '{channel}' for user {user.phone_no}")
        return {'success': False, 'error': f'Unknown channel: {channel}'}
