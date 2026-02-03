import requests
import json
from .models import ExternalAPI
from django.utils import timezone

# Global variable to track current user phone during request processing
# This gets set in whatsapp.py before calling execute_tool
_current_user_phone = None
_current_admin = None
_current_org = None

def set_current_context(phone, admin, org=None):
    """Set the current user context for built-in tools like apply_tag"""
    global _current_user_phone, _current_admin, _current_org
    _current_user_phone = phone
    _current_admin = admin
    _current_org = org

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
    from django.utils import timezone
    
    user_phone = phone or _current_user_phone
    if not user_phone:
        return "Error: No user phone number available"
    
    # Find the tag - check organization first, then admin
    tag = None
    if _current_org:
        tag = Tag.objects.filter(organization=_current_org, name__iexact=tag_name).first()
    if not tag and admin:
        tag = Tag.objects.filter(admin=admin, name__iexact=tag_name).first()
    if not tag:
        return f"Error: Tag '{tag_name}' not found"
    
    # Find the user - check by organization first, then admin
    user = None
    if _current_org:
        user = User.objects.filter(phone_no__endswith=user_phone[-10:], organization=_current_org).first()
    if not user and admin:
        user = User.objects.filter(phone_no__endswith=user_phone[-10:], admin_id=admin).first()
    if not user:
        # Try without org/admin filter as fallback
        user = User.objects.filter(phone_no__endswith=user_phone[-10:]).first()
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
    from django.utils import timezone
    
    user_phone = phone or _current_user_phone
    if not user_phone:
        return "Error: No user phone number available"
    
    # Find the tag - check organization first, then admin
    tag = None
    if _current_org:
        tag = Tag.objects.filter(organization=_current_org, name__iexact=tag_name).first()
    if not tag and admin:
        tag = Tag.objects.filter(admin=admin, name__iexact=tag_name).first()
    if not tag:
        return f"Error: Tag '{tag_name}' not found"
    
    # Find the user - check by organization first, then admin
    user = None
    if _current_org:
        user = User.objects.filter(phone_no__endswith=user_phone[-10:], organization=_current_org).first()
    if not user and admin:
        user = User.objects.filter(phone_no__endswith=user_phone[-10:], admin_id=admin).first()
    if not user:
        user = User.objects.filter(phone_no__endswith=user_phone[-10:]).first()
    if not user:
        return f"Error: User with phone {user_phone} not found"
    
    # Remove the tag
    deleted_count, _ = UserTag.objects.filter(user=user, tag=tag).delete()
    
    if deleted_count > 0:
        print(f"[Tag] Removed '{tag_name}' from user {user_phone}")
        return f"Success: Tag '{tag_name}' removed from user"
    else:
        return f"Info: User did not have tag '{tag_name}'"




def apply_custom_field_value(field_name, field_value, admin, phone=None):
    """
    Set a custom field value for a user by phone number or current context.

    Args:
        field_name (str): Name of the custom field to set
        field_value (str): Value to set for the custom field
        admin (Admin): Admin instance
        phone (str): Phone number (optional, uses current context if not provided)

    Returns:
        str: Success or error message
    """
    from .models import CustomField, CustomFieldValue, User

    user_phone = phone or _current_user_phone
    if not user_phone:
        return "Error: No user phone number available"

    # Find the custom field - check organization first, then admin
    custom_field = None
    if _current_org:
        custom_field = CustomField.objects.filter(
            organization=_current_org,
            name__iexact=field_name,
            is_active=True
        ).first()
    if not custom_field and admin:
        custom_field = CustomField.objects.filter(
            admin=admin,
            name__iexact=field_name,
            is_active=True
        ).first()
    if not custom_field:
        return f"Error: Custom field '{field_name}' not found"

    # Find the user - check by organization first, then admin
    user = None
    if _current_org:
        user = User.objects.filter(
            phone_no__endswith=user_phone[-10:],
            organization=_current_org
        ).first()
    if not user and admin:
        user = User.objects.filter(
            phone_no__endswith=user_phone[-10:],
            admin_id=admin
        ).first()
    if not user:
        # Try without org/admin filter as fallback
        user = User.objects.filter(phone_no__endswith=user_phone[-10:]).first()
    if not user:
        return f"Error: User with phone {user_phone} not found"

    # Create or update the custom field value
    field_value_obj, created = CustomFieldValue.objects.update_or_create(
        custom_field=custom_field,
        user=user,
        defaults={
            'value': field_value.strip(),
            'updated_at': timezone.now()
        }
    )

    action = "Set" if created else "Updated"
    print(f"[CustomField] {action} '{field_name}' to '{field_value}' for user {user_phone}")
    return f"Success: {action} custom field '{field_name}' to '{field_value}'"


def get_user_custom_fields_for_ai(admin, phone=None):
    """
    Get all custom field values for a user, formatted for AI context.

    Args:
        admin (Admin): Admin instance
        phone (str): Phone number (optional, uses current context if not provided)

    Returns:
        str: Formatted string of custom field values for AI context
    """
    from .models import CustomField, CustomFieldValue, User

    user_phone = phone or _current_user_phone
    if not user_phone:
        return ""

    # Find the user
    user = None
    if _current_org:
        user = User.objects.filter(
            phone_no__endswith=user_phone[-10:],
            organization=_current_org
        ).first()
    if not user and admin:
        user = User.objects.filter(
            phone_no__endswith=user_phone[-10:],
            admin_id=admin
        ).first()
    if not user:
        user = User.objects.filter(phone_no__endswith=user_phone[-10:]).first()
    if not user:
        return ""

    # Get all custom field values for this user
    field_values = CustomFieldValue.objects.filter(
        user=user,
        custom_field__is_active=True
    ).select_related('custom_field')

    if not field_values:
        return "No custom fields captured yet."

    # Format for AI context
    lines = ["User's Captured Custom Fields:"]
    for fv in field_values:
        lines.append(f"- {fv.custom_field.name}: {fv.value}")

    return "\n".join(lines)

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
        
        if tool_name == "apply_custom_field":
            field_name = arguments.get("field_name", "")
            field_value = arguments.get("field_value", "")
            return apply_custom_field_value(field_name, field_value, admin)
        
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

