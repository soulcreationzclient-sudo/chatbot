import requests
import json
from .models import ExternalAPI

# Global variable to track current user phone during request processing
# This gets set in whatsapp.py before calling execute_tool
_current_user_phone = None
_current_admin = None

def set_current_context(phone, admin):
    """Set the current user context for built-in tools like apply_tag"""
    global _current_user_phone, _current_admin
    _current_user_phone = phone
    _current_admin = admin

def apply_user_tag(tag_name, admin, phone=None):
    """
    Apply a tag to a user by phone number or current context.
    
    Args:
        tag_name (str): Name of the tag to apply
        admin (Admin): Admin instance
        phone (str): Phone number (optional, uses current context if not provided)
        
    Returns:
        str: Success or error message
    """
    from .models import Tag, UserTag, User
    
    user_phone = phone or _current_user_phone
    if not user_phone:
        return "Error: No user phone number available"
    
    # Find the tag
    tag = Tag.objects.filter(admin=admin, name__iexact=tag_name).first()
    if not tag:
        return f"Error: Tag '{tag_name}' not found"
    
    # Find the user
    user = User.objects.filter(phone_no__endswith=user_phone[-10:], admin_id=admin).first()
    if not user:
        return f"Error: User with phone {user_phone} not found"
    
    # Apply the tag (create if not exists)
    user_tag, created = UserTag.objects.get_or_create(user=user, tag=tag)
    
    if created:
        print(f"[Tag] Applied '{tag_name}' to user {user_phone}")
        return f"Success: Tag '{tag_name}' applied to user"
    else:
        return f"Info: User already has tag '{tag_name}'"

def remove_user_tag(tag_name, admin, phone=None):
    """
    Remove a tag from a user by phone number or current context.
    
    Args:
        tag_name (str): Name of the tag to remove
        admin (Admin): Admin instance
        phone (str): Phone number (optional, uses current context if not provided)
        
    Returns:
        str: Success or error message
    """
    from .models import Tag, UserTag, User
    
    user_phone = phone or _current_user_phone
    if not user_phone:
        return "Error: No user phone number available"
    
    # Find the tag
    tag = Tag.objects.filter(admin=admin, name__iexact=tag_name).first()
    if not tag:
        return f"Error: Tag '{tag_name}' not found"
    
    # Find the user
    user = User.objects.filter(phone_no__endswith=user_phone[-10:], admin_id=admin).first()
    if not user:
        return f"Error: User with phone {user_phone} not found"
    
    # Remove the tag
    deleted_count, _ = UserTag.objects.filter(user=user, tag=tag).delete()
    
    if deleted_count > 0:
        print(f"[Tag] Removed '{tag_name}' from user {user_phone}")
        return f"Success: Tag '{tag_name}' removed from user"
    else:
        return f"Info: User did not have tag '{tag_name}'"


def execute_tool(tool_name, arguments, admin):
    """
    Execute a defined ExternalAPI tool or built-in function.
    
    Args:
        tool_name (str): Name of the tool to execute
        arguments (dict): Dictionary of arguments extracted by AI (e.g. {"booking_id": "123"})
        admin (Admin): The admin instance to look up tools for
        
    Returns:
        str: JSON response string or error message
    """
    try:
        # Handle built-in functions first
        if tool_name == "apply_tag":
            tag_name = arguments.get("tag_name", "")
            return apply_user_tag(tag_name, admin)
        
        # Find the tool config from ExternalAPI
        tool_config = ExternalAPI.objects.filter(admin=admin, name=tool_name).first()
        if not tool_config:
            return f"Error: Tool '{tool_name}' not configured."

        # Prepare URL and Payload with variable substitution
        # We use simple string replacement for {{variable}} style placeholders
        
        target_url = tool_config.url
        target_payload = tool_config.payload or {}
        target_headers = tool_config.headers or {}

        # Replace in URL
        for key, value in arguments.items():
            placeholder = "{{" + key + "}}"
            target_url = target_url.replace(placeholder, str(value))

        # Replace in Payload (recursively if needed, but let's stick to simple string dump for now)
        # Convert payload to string, replace, then parse back to JSON could be unsafe but easiest for flexible schemas
        payload_str = json.dumps(target_payload)
        for key, value in arguments.items():
            placeholder = "{{" + key + "}}"
            payload_str = payload_str.replace(placeholder, str(value))
            
        final_payload = json.loads(payload_str)

        # Execute Request
        method = tool_config.method.upper()
        
        if method == 'GET':
            response = requests.get(target_url, headers=target_headers, params=final_payload)
        elif method == 'POST':
            response = requests.post(target_url, headers=target_headers, json=final_payload)
        else:
            return f"Error: Unsupported method {method}"

        # Return results
        try:
            return json.dumps(response.json())
        except:
            return response.text

    except Exception as e:
        return f"Error executing tool {tool_name}: {str(e)}"

