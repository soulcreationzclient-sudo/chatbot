"""
Custom Field Processor for WhatsApp Messages

This module handles the processing of {{custom_field:field_name:value}} tags in AI responses,
allowing the chatbot to extract and save user details (name, address, phone, etc.) from conversations.

Usage in AI prompts:
    "Thanks for your order, {{custom_field:name:John Doe}}!"
    "Your order will be delivered to: {{custom_field:address:123 Main St}}"

The processor will:
1. Parse the {{custom_field:xxx:yyy}} tags from the response
2. Look up the corresponding CustomField definition
3. Validate the value based on field type
4. Save/update the CustomFieldValue for the user
5. Return the processed text with tags replaced by descriptions
"""

import re
from django.db import transaction
from django.utils import timezone


def parse_custom_field_tags(text):
    """
    Extract all {{custom_field:field_name:value}} tags from text.

    Args:
        text: The response text containing potential custom field tags

    Returns:
        List of tuples: [(full_tag, field_name, field_value), ...]
        Example: [('{{custom_field:name:John Doe}}', 'name', 'John Doe')]
    """
    # Pattern matches: {{custom_field:field_name:value}}
    # Field name: alphanumeric and underscores
    # Value: any characters except }}
    pattern = r'\{\{custom_field:([a-zA-Z0-9_]+):(.+?)\}\}'
    matches = re.findall(pattern, text)

    # Find full tags for replacement
    full_tags = re.findall(r'\{\{custom_field:[a-zA-Z0-9_]+:.+?\}\}', text)

    return list(zip(full_tags, [m[0] for m in matches], [m[1] for m in matches]))


def get_custom_field(field_name, admin, organization=None):
    """
    Look up a CustomField by name for a specific admin or organization.

    Args:
        field_name: The custom field name (e.g., 'name', 'address')
        admin: The Admin model instance
        organization: The Organization model instance (optional)

    Returns:
        CustomField instance or None if not found
    """
    from newapp.models import CustomField
    try:
        # First try to find by organization
        if organization:
            field = CustomField.objects.filter(
                organization=organization,
                name=field_name,
                is_active=True
            ).first()
            if field:
                return field

        # Fallback to admin if no org specific field or org not provided
        if admin:
            field = CustomField.objects.filter(
                admin=admin,
                name=field_name,
                is_active=True
            ).first()
            if field:
                return field

        return None
    except Exception as e:
        print(f"[CustomField] Error looking up custom field '{field_name}': {e}")
        return None


def validate_field_value(field, value):
    """
    Validate a custom field value against the custom field's type.

    Args:
        field: CustomField instance
        value: The value to validate (string)

    Returns:
        tuple: (is_valid: bool, cleaned_value: any, error_message: str)
    """
    if not value or not value.strip():
        return (False, None, "Value cannot be empty")

    value = value.strip()

    # Field type specific validation
    field_type = field.field_type

    if field_type == 'email':
        # Basic email validation
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, value):
            return (False, None, "Invalid email format")
        return (True, value, None)

    elif field_type == 'number':
        try:
            # Strip currency symbols and common prefixes before validation
            cleaned_num = re.sub(r'[^\d.,\-]', '', value)  # Remove everything except digits, dots, commas, minus
            if not cleaned_num:
                return (False, None, "Value must be a number")
            float(cleaned_num.replace(',', ''))
            return (True, cleaned_num.replace(',', ''), None)
        except ValueError:
            return (False, None, f"Value must be a number (got: {value})")

    elif field_type == 'phone':
        # Accept various phone formats, just basic validation
        # Remove common separators and check if it has digits
        phone_digits = re.sub(r'[^\d]', '', value)
        if len(phone_digits) < 7:
            return (False, None, "Phone number must have at least 7 digits")
        return (True, value, None)

    elif field_type == 'date':
        # Try to parse as date
        from datetime import datetime
        try:
            # Try multiple date formats
            for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y/%m/%d', '%d-%m-%Y']:
                try:
                    datetime.strptime(value, fmt)
                    return (True, value, None)
                except ValueError:
                    continue
            return (False, None, "Invalid date format. Use YYYY-MM-DD or DD/MM/YYYY")
        except Exception:
            return (False, None, "Invalid date format")

    elif field_type == 'datetime':
        # Try to parse as datetime
        from datetime import datetime
        try:
            datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
            return (True, value, None)
        except ValueError:
            return (False, None, "Invalid datetime format. Use YYYY-MM-DD HH:MM:SS")

    elif field_type == 'boolean':
        # Accept various boolean representations
        value_lower = value.lower()
        if value_lower in ['yes', 'true', '1', 'y', 'on']:
            return (True, 'true', None)
        elif value_lower in ['no', 'false', '0', 'n', 'off']:
            return (True, 'false', None)
        else:
            return (False, None, "Value must be Yes/No, True/False, or 1/0")

    elif field_type in ['text', 'textarea', 'select']:
        # No specific validation for these types
        return (True, value, None)

    else:
        # Unknown field type, accept as-is
        return (True, value, None)


def save_custom_field_value(field, user, value, admin, organization=None):
    """
    Save or update a custom field value for a user.

    Args:
        field: CustomField instance
        user: User model instance
        value: The value to save (already validated)
        admin: Admin model instance
        organization: Organization instance (optional)

    Returns:
        tuple: (success: bool, message: str, field_value: CustomFieldValue or None)
    """
    from newapp.models import CustomFieldValue
    try:
        with transaction.atomic():
            # Try to update existing value or create new one
            field_value, created = CustomFieldValue.objects.update_or_create(
                custom_field=field,
                user=user,
                defaults={
                    'value': value,
                    'updated_at': timezone.now()
                }
            )

            action = "Created" if created else "Updated"
            print(f"[CustomField] {action} custom field '{field.name}' for user {user.phone_no}: {value}")

            return (True, f"{action} {field.name}: {value}", field_value)

    except Exception as e:
        print(f"[CustomField] Error saving custom field value: {e}")
        return (False, f"Error saving field: {str(e)}", None)


def format_custom_field_for_display(field, value):
    """
    Format a custom field value for display in the response text.

    Args:
        field: CustomField instance
        value: The stored value

    Returns:
        Formatted string for display
    """
    if not value:
        return ""

    if field.field_type == 'boolean':
        return "Yes" if value == 'true' else "No"

    return value


def process_response_with_custom_fields(response_text, admin, user, organization=None):
    """
    Process an AI response, extracting and saving any {{custom_field:field_name:value}} tags.

    This is the main function to call from the WhatsApp controller.

    Args:
        response_text: The full AI response text
        admin: The Admin model instance
        user: User model instance
        organization: Organization model instance (optional)

    Returns:
        dict with:
            - 'success': bool - Whether processing completed without errors
            - 'fields_processed': int - Number of custom fields successfully processed
            - 'fields_failed': int - Number of custom fields that failed validation
            - 'final_text': str - The text with custom field tags replaced by descriptions
            - 'processed_fields': list - Details of processed fields
    """
    result = {
        'success': True,
        'fields_processed': 0,
        'fields_failed': 0,
        'final_text': response_text,
        'processed_fields': []
    }

    # Parse custom field tags
    field_tags = parse_custom_field_tags(response_text)

    if not field_tags:
        # No custom field tags found - log for debugging
        has_curly = '{{' in response_text
        if has_curly:
            print(f"[CustomField] WARNING: Response contains '{{{{' but no custom_field tags found. First 300 chars: {response_text[:300]}")
        else:
            print(f"[CustomField] No custom field tags in response (first 100 chars: {response_text[:100]})")
        return result

    print(f"[CustomField] Found {len(field_tags)} custom field tag(s) in response")

    # Process each custom field tag
    remaining_text = response_text
    processed_fields = []

    for full_tag, field_name, field_value in field_tags:
        # Look up the custom field definition
        custom_field = get_custom_field(field_name, admin, organization)

        if not custom_field:
            print(f"[CustomField] Warning: Custom field '{field_name}' not found")
            # Keep the tag in the text but mark as failed
            result['fields_failed'] += 1
            result['success'] = False
            processed_fields.append({
                'field_name': field_name,
                'value': field_value,
                'status': 'not_found',
                'message': f"Custom field '{field_name}' not defined"
            })
            continue

        # Validate the value
        is_valid, cleaned_value, error_message = validate_field_value(custom_field, field_value)

        if not is_valid:
            print(f"[CustomField] Validation failed for '{field_name}': {error_message}")
            result['fields_failed'] += 1
            result['success'] = False
            processed_fields.append({
                'field_name': field_name,
                'value': field_value,
                'status': 'validation_failed',
                'message': error_message
            })
            continue

        # Save the value to the database
        success, message, field_value_obj = save_custom_field_value(
            custom_field, user, cleaned_value, admin, organization
        )

        if success:
            result['fields_processed'] += 1
            # Format the value for display
            display_value = format_custom_field_for_display(custom_field, cleaned_value)
            # Remove the tag completely from the message (value already saved)
            remaining_text = remaining_text.replace(full_tag, '').strip()
            processed_fields.append({
                'field_name': field_name,
                'value': cleaned_value,
                'status': 'success',
                'message': message
            })
        else:
            result['fields_failed'] += 1
            result['success'] = False
            processed_fields.append({
                'field_name': field_name,
                'value': field_value,
                'status': 'save_failed',
                'message': message
            })

    # Clean up extra whitespace/newlines from removed tags
    remaining_text = re.sub(r'\n\s*\n', '\n\n', remaining_text).strip()
    result['final_text'] = remaining_text
    result['processed_fields'] = processed_fields

    print(f"[CustomField] Processing complete. Processed: {result['fields_processed']}, Failed: {result['fields_failed']}")
    return result


def get_user_custom_fields(user, admin, organization=None):
    """
    Get all custom field values for a user, formatted for AI context.

    Args:
        user: User model instance
        admin: Admin model instance
        organization: Organization model instance (optional)

    Returns:
        dict: {field_name: value, ...}
    """
    from newapp.models import CustomField, CustomFieldValue

    try:
        # Get all active custom fields for this admin/org
        if organization:
            fields = CustomField.objects.filter(
                organization=organization,
                is_active=True
            ).exclude(values__user=user)
        else:
            fields = CustomField.objects.filter(
                admin=admin,
                is_active=True
            ).exclude(values__user=user)

        # Get all field values for this user
        field_values = CustomFieldValue.objects.filter(
            user=user,
            custom_field__is_active=True
        ).select_related('custom_field')

        # Build the result dict
        result = {}
        for fv in field_values:
            field_name = fv.custom_field.name
            # If field has organization, prefix it to avoid conflicts
            if fv.custom_field.organization:
                field_name = f"{fv.custom_field.organization.name}_{fv.custom_field.name}"
            result[field_name] = fv.value

        return result

    except Exception as e:
        print(f"[CustomField] Error getting user custom fields: {e}")
        return {}


def format_custom_fields_for_ai_context(user_custom_fields):
    """
    Format custom field values for inclusion in AI prompt context.

    Args:
        user_custom_fields: dict of {field_name: value}

    Returns:
        str: Formatted string for AI context
    """
    if not user_custom_fields:
        return "No custom fields captured yet."

    lines = ["User's Captured Custom Fields:"]
    for field_name, value in user_custom_fields.items():
        lines.append(f"- {field_name}: {value}")

    return "\n".join(lines)


def format_custom_fields_for_inbox(user, admin, organization=None):
    """
    Get all custom field values for a user, formatted for display in inbox sidebar.

    Args:
        user: User model instance
        admin: Admin model instance
        organization: Organization model instance (optional)

    Returns:
        list of dict: [{'id': field_value_id, 'field_name': str, 'value': str, 'field_type': str, 'description': str}, ...]
    """
    from newapp.models import CustomFieldValue

    try:
        field_values = CustomFieldValue.objects.filter(
            user=user,
            custom_field__is_active=True
        ).select_related('custom_field').order_by('custom_field__name')

        result = []
        for fv in field_values:
            result.append({
                'id': fv.id,
                'field_name': fv.custom_field.name,
                'field_type': fv.custom_field.field_type,
                'description': fv.custom_field.description or '',
                'value': fv.value or '',
                'updated_at': fv.updated_at
            })

        return result

    except Exception as e:
        print(f"[CustomField] Error formatting fields for inbox: {e}")
        return []
