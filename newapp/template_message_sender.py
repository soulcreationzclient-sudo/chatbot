"""
Template Message Sender Utility
Sends WhatsApp template messages via Meta Graph API.
Used by: Follow-up system, Pipeline automation, AI tags.
"""
import json
import logging
import requests

logger = logging.getLogger(__name__)


def send_template_message(phone_number, template, variables=None, phone_id=None, token=None, organization=None):
    """
    Send a WhatsApp template message via Meta Graph API.

    Args:
        phone_number: Recipient phone number (E.164 format or without +)
        template: WhatsAppTemplate model instance
        variables: dict of variable mappings, e.g. {"1": "John", "2": "Order #123"}
        phone_id: WhatsApp Phone Number ID (from org settings)
        token: WhatsApp API token (from org settings)
        organization: Organization instance (auto-loads phone_id and token if not provided)

    Returns:
        dict with success status and response data
    """
    if not variables:
        variables = {}

    # Auto-load credentials from organization
    if organization and not phone_id:
        phone_id = organization.whatsapp_phone_id
    if organization and not token:
        token = organization.whatsapp_token

    if not phone_id or not token:
        logger.error("Missing WhatsApp credentials for template message")
        return {'success': False, 'error': 'Missing WhatsApp credentials'}

    if not phone_number:
        return {'success': False, 'error': 'Missing phone number'}

    # Build template components
    components = []

    # Parse template components from the stored template
    template_components = template.components if isinstance(template.components, list) else json.loads(template.components) if template.components else []

    for comp in template_components:
        comp_type = comp.get('type', '').upper()

        if comp_type == 'HEADER':
            header_format = comp.get('format', 'TEXT')
            if header_format == 'IMAGE' and variables.get('header_image'):
                components.append({
                    "type": "header",
                    "parameters": [{
                        "type": "image",
                        "image": {"link": variables['header_image']}
                    }]
                })
            elif header_format == 'DOCUMENT' and variables.get('header_document'):
                components.append({
                    "type": "header",
                    "parameters": [{
                        "type": "document",
                        "document": {"link": variables['header_document']}
                    }]
                })

        elif comp_type == 'BODY':
            # Body parameters (positional: {{1}}, {{2}}, etc.)
            body_params = []
            param_index = 1
            while str(param_index) in variables:
                body_params.append({
                    "type": "text",
                    "text": str(variables[str(param_index)])
                })
                param_index += 1

            if body_params:
                components.append({
                    "type": "body",
                    "parameters": body_params
                })

        elif comp_type == 'BUTTON':
            # Handle button parameters (e.g., URL suffix)
            buttons = comp.get('buttons', [])
            for idx, button in enumerate(buttons):
                if button.get('type') == 'URL' and variables.get(f'button_{idx}'):
                    components.append({
                        "type": "button",
                        "sub_type": "url",
                        "index": str(idx),
                        "parameters": [{
                            "type": "text",
                            "text": variables[f'button_{idx}']
                        }]
                    })

    # Build the API payload
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "template",
        "template": {
            "name": template.name,
            "language": {
                "code": template.language or "en"
            }
        }
    }

    if components:
        payload["template"]["components"] = components

    # Send via Meta Graph API
    url = f"https://graph.facebook.com/v18.0/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response_data = response.json()

        if response.status_code in (200, 201):
            logger.info(f"Template message sent to {phone_number}: {template.name}")
            return {
                'success': True,
                'message_id': response_data.get('messages', [{}])[0].get('id'),
                'response': response_data
            }
        else:
            logger.error(f"Template message failed: {response_data}")
            return {
                'success': False,
                'error': response_data.get('error', {}).get('message', 'Unknown error'),
                'response': response_data
            }

    except requests.exceptions.RequestException as e:
        logger.error(f"Template message request error: {str(e)}")
        return {'success': False, 'error': str(e)}


def send_pipeline_stage_template(opportunity, new_stage):
    """
    Send auto-message template when an opportunity moves to a stage.
    Called from pipeline.opportunity_move().

    Args:
        opportunity: Opportunity model instance
        new_stage: PipelineStage model instance (with auto_send_enabled)
    """
    if not new_stage.auto_send_enabled or not new_stage.auto_send_template:
        return None

    # Get the user's phone number from the opportunity
    if not opportunity.user or not opportunity.user.phone_no:
        logger.warning(f"Opportunity {opportunity.id} has no user with phone number, skipping auto-send")
        return None

    # Get organization for credentials
    org = None
    if opportunity.organization_id:
        from .models import Organization
        org = Organization.objects.filter(id=opportunity.organization_id).first()

    if not org:
        logger.error(f"No organization found for opportunity {opportunity.id}")
        return None

    # Build variables from opportunity and user data
    variables = dict(new_stage.template_variables) if new_stage.template_variables else {}

    # Auto-populate common variables if not explicitly set
    # Only add params if the template body actually expects them (contains {{1}})
    if opportunity.user:
        template = new_stage.auto_send_template
        template_components = template.components if isinstance(template.components, list) else json.loads(template.components) if template.components else []
        body_has_params = False
        for comp in template_components:
            if comp.get('type', '').upper() == 'BODY':
                body_text = comp.get('text', '')
                if '{{1}}' in body_text:
                    body_has_params = True
                break
        if body_has_params and '1' not in variables and opportunity.user.name:
            variables['1'] = opportunity.user.name  # First param often is customer name

    result = send_template_message(
        phone_number=opportunity.user.phone_no,
        template=new_stage.auto_send_template,
        variables=variables,
        organization=org
    )

    if result.get('success'):
        logger.info(f"Auto-sent template '{new_stage.auto_send_template.name}' to {opportunity.user.phone_no} on stage '{new_stage.name}'")
    else:
        logger.error(f"Failed auto-send: {result.get('error')}")

    return result
