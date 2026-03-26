import requests
import json
from .models import ExternalAPI
from django.utils import timezone
from newapp.logging_config import get_logger
tag_logger = get_logger('webhook')

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
    
    tag = None
    if _current_org:
        tag = Tag.objects.filter(organization=_current_org, name__iexact=tag_name).first()
        tag_logger.info(f"[Tag] Org filter: org={_current_org.id}, tag_name={tag_name}, found={tag is not None}")
    if not tag and admin:
        tag = Tag.objects.filter(admin=admin, name__iexact=tag_name).first()
        tag_logger.info(f"[Tag] Admin filter: admin={admin.id}, tag_name={tag_name}, found={tag is not None}")
    if not tag:
        # Try without org/admin filter as fallback
        tag = Tag.objects.filter(name__iexact=tag_name).first()
        tag_logger.info(f"[Tag] Global filter: tag_name={tag_name}, found={tag is not None}")
    if not tag:
        tag_logger.warning(f"[Tag] Tag '{tag_name}' not found in any scope")
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
    
    # Always trigger pipeline automations when tag is applied (even if already existed)
    try:
        from .controllers.pipeline import run_pipeline_automations
        tag_logger.info(f"[Tag] Calling run_pipeline_automations(user_id={user.id}, tag_id={tag.id}, tag_name={tag_name})")
        run_pipeline_automations(user.id, 'tag_applied', tag_id=tag.id)
        tag_logger.info(f"[Tag] Pipeline automations completed for tag '{tag_name}' on user {user_phone}")
    except Exception as e:
        tag_logger.error(f"[Tag] Pipeline automation error: {e}", exc_info=True)
    
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
    
    # Trigger pipeline automations on custom field change
    try:
        from .controllers.pipeline import run_pipeline_automations
        run_pipeline_automations(
            user.id,
            'custom_field_changed',
            field_name=field_name,
            field_value=field_value.strip()
        )
    except Exception as e:
        print(f"[CustomField] Pipeline automation error: {e}")
    
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
        
        # Find the tool config from ExternalAPI - check org first, then admin
        tool_config = None
        if _current_org:
            tool_config = ExternalAPI.objects.filter(organization=_current_org, name=tool_name).first()
        if not tool_config and admin:
            tool_config = ExternalAPI.objects.filter(admin=admin, name=tool_name).first()
        if not tool_config:
            return f"Error: Tool '{tool_name}' not configured."

        # Prepare URL and Payload with variable substitution
        target_url = tool_config.url
        target_payload = tool_config.payload or {}
        target_headers = tool_config.headers or {}

        # Replace in URL - handle both {key} and {{key}} formats
        for key, value in arguments.items():
            target_url = target_url.replace("{" + key + "}", str(value))
            target_url = target_url.replace("{{" + key + "}}", str(value))

        # Replace in Payload - handle both formats
        payload_str = json.dumps(target_payload)
        for key, value in arguments.items():
            payload_str = payload_str.replace("{" + key + "}", str(value))
            payload_str = payload_str.replace("{{" + key + "}}", str(value))
            payload_str = payload_str.replace("{{custom_field:" + key + ":value}}", str(value))
            
        final_payload = json.loads(payload_str)

        # Execute Request
        method = tool_config.method.upper()
        
        if method == 'GET':
            response = requests.get(target_url, headers=target_headers, params=final_payload, timeout=30)
        elif method == 'POST':
            if tool_config.body_type == 'form':
                response = requests.post(target_url, headers=target_headers, data=final_payload, timeout=30)
            else:
                response = requests.post(target_url, headers=target_headers, json=final_payload, timeout=30)
        elif method == 'PUT':
            response = requests.put(target_url, headers=target_headers, json=final_payload, timeout=30)
        elif method == 'PATCH':
            response = requests.patch(target_url, headers=target_headers, json=final_payload, timeout=30)
        elif method == 'DELETE':
            response = requests.delete(target_url, headers=target_headers, timeout=30)
        else:
            return f"Error: Unsupported method {method}"

        # Process response mapping - save fields to custom fields
        response_data = None
        try:
            response_data = response.json()
        except:
            pass
        
        if response_data and tool_config.response_mapping:
            _process_response_mapping(tool_config.response_mapping, response_data, admin)

        # Return results
        try:
            return json.dumps(response.json())
        except:
            return response.text

    except Exception as e:
        return f"Error executing tool {tool_name}: {str(e)}"


def _process_response_mapping(mappings, response_data, admin):
    """
    Process response mapping: extract fields from API response and save to custom fields.
    
    Args:
        mappings: List of {"jsonpath": "field.path", "custom_field": "field_name"} dicts
        response_data: The API response data (dict or list)
        admin: Admin instance
    """
    for mapping in mappings:
        jsonpath = mapping.get('jsonpath', '').strip()
        field_name = mapping.get('custom_field', '').strip()
        
        if not jsonpath or not field_name:
            continue
        
        # Simple dot-path traversal (e.g., "data.balance" or "result.name")
        try:
            value = response_data
            for key in jsonpath.split('.'):
                if isinstance(value, dict):
                    value = value.get(key)
                elif isinstance(value, list) and key.isdigit():
                    value = value[int(key)]
                else:
                    value = None
                    break
            
            if value is not None:
                apply_custom_field_value(field_name, str(value), admin)
                print(f"[ResponseMapping] Saved '{jsonpath}' → '{field_name}' = '{value}'")
        except Exception as e:
            print(f"[ResponseMapping] Error mapping '{jsonpath}' → '{field_name}': {e}")

