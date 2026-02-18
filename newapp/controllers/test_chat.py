from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import json
import re
from newapp.models import ChatGPTPrompt, Admin, Organization
from datetime import datetime


def test_chat(request):
    """
    Simple chat interface for testing prompts - redirects to dashboard with chat tab.
    """
    return redirect('/webchat/dashboard/?tab=test-chat')


def _parse_ai_response(raw_response):
    """
    Parse AI response to extract clean text, tags, and custom fields.
    Returns dict with 'clean_text', 'tags', 'custom_fields', 'raw_response'.
    """
    tags = []
    custom_fields = []
    clean_text = raw_response

    # --- Try to extract text from JSON ---
    stripped = raw_response.strip()
    # Strip markdown code fences
    if stripped.startswith('```'):
        stripped = re.sub(r'^```(?:json)?\s*', '', stripped)
        stripped = re.sub(r'\s*```$', '', stripped)
        stripped = stripped.strip()

    if stripped.startswith('{') or stripped.startswith('['):
        try:
            data_json = json.loads(stripped)
            messages = data_json.get("messages", [])
            text_parts = []
            if messages and isinstance(messages, list):
                for msg_item in messages:
                    if isinstance(msg_item, dict):
                        t = msg_item.get("text")
                        if not t:
                            t = msg_item.get("message", {}).get("text", "")
                        if t and isinstance(t, str) and t.strip():
                            text_parts.append(t.strip())
            if text_parts:
                clean_text = "\n\n".join(text_parts)
        except (json.JSONDecodeError, AttributeError):
            # Try regex fallback
            text_matches = re.findall(r'"text"\s*:\s*"((?:[^"\\]|\\.)*)"', stripped)
            if text_matches:
                extracted = []
                for t in text_matches:
                    t = t.replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')
                    if t.strip():
                        extracted.append(t.strip())
                if extracted:
                    clean_text = "\n\n".join(extracted)

    # --- Extract tags from text ---
    tag_matches = re.findall(r'\{\{tag:add:([^}]+)\}\}', clean_text)
    for tag_name in tag_matches:
        tags.append(tag_name.strip())
    # Remove tag markers from clean text
    clean_text = re.sub(r'\s*\{\{tag:add:[^}]+\}\}\s*', '', clean_text).strip()

    # --- Extract custom fields from text ---
    cf_matches = re.findall(r'\{\{custom_field:([a-zA-Z0-9_]+):(.+?)\}\}', clean_text)
    for field_name, field_value in cf_matches:
        custom_fields.append({'name': field_name, 'value': field_value.strip()})
    # Remove custom field markers from clean text
    clean_text = re.sub(r'\s*\{\{custom_field:[a-zA-Z0-9_]+:.+?\}\}\s*', '', clean_text).strip()

    # --- Clean up extra whitespace ---
    clean_text = re.sub(r'\n\s*\n\s*\n', '\n\n', clean_text)

    return {
        'clean_text': clean_text,
        'tags': tags,
        'custom_fields': custom_fields,
        'raw_response': raw_response,
    }


@csrf_exempt
@require_http_methods(["POST"])
def test_chat_send(request):
    """
    Handle chat messages for testing from the dashboard.
    Calls OpenAI directly for quick testing.
    """
    try:
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
        prompt_id = data.get('prompt_id', None)

        if not user_message:
            return JsonResponse({
                'status': 'error',
                'message': 'Please enter a message'
            })

        # Always use the prompt from Settings (ChatGPTPrompt)
        prompt_obj = ChatGPTPrompt.objects.order_by('-updated_at').first()
        system_prompt = prompt_obj.prompt_text if prompt_obj else "You are a helpful assistant."

        # Get OpenAI API key from organization or admin
        openai_key = None
        gpt_model = 'gpt-4o-mini'
        org_id = request.session.get('organization_id')
        admin_id = request.session.get('admin_id')
        
        if org_id:
            try:
                org = Organization.objects.get(id=org_id)
                openai_key = org.openai_api_key
                gpt_model = getattr(org, 'gpt_model', 'gpt-4o-mini')
            except Organization.DoesNotExist:
                pass
        
        if not openai_key and admin_id:
            try:
                admin = Admin.objects.get(id=admin_id)
                openai_key = admin.openai_api_key
            except Admin.DoesNotExist:
                pass

        # Call OpenAI if we have a key
        if openai_key:
            try:
                from openai import OpenAI
                client = OpenAI(api_key=openai_key)
                
                response = client.chat.completions.create(
                    model=gpt_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ]
                )
                ai_response = response.choices[0].message.content
            except Exception as e:
                ai_response = f"AI Error: {str(e)}"
        else:
            ai_response = f"Test Mode: You said '{user_message}'. (No OpenAI API key configured)"

        # Parse the response to extract clean text, tags, and custom fields
        parsed = _parse_ai_response(ai_response)

        # Return response
        now = datetime.now().isoformat()
        
        return JsonResponse({
            'status': 'success',
            'user_message': {
                'content': user_message,
                'created_at': now
            },
            'bot_message': {
                'content': parsed['clean_text'],
                'raw_content': parsed['raw_response'],
                'tags': parsed['tags'],
                'custom_fields': parsed['custom_fields'],
                'created_at': now
            }
        })

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        })


@csrf_exempt
@require_http_methods(["POST"])
def test_chat_quick(request):
    """
    Quick test endpoint - just send message and get response.
    """
    try:
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()

        if not user_message:
            return JsonResponse({
                'status': 'error',
                'message': 'Please enter a message'
            })

        # Get default prompt
        prompt_obj = ChatGPTPrompt.objects.order_by('-updated_at').first()
        system_prompt = prompt_obj.prompt_text if prompt_obj else "You are a helpful assistant."

        # Get OpenAI API key
        openai_key = None
        org_id = request.session.get('organization_id')
        admin_id = request.session.get('admin_id')
        
        if org_id:
            try:
                org = Organization.objects.get(id=org_id)
                openai_key = org.openai_api_key
            except Organization.DoesNotExist:
                pass
        
        if not openai_key and admin_id:
            try:
                admin = Admin.objects.get(id=admin_id)
                openai_key = admin.openai_api_key
            except Admin.DoesNotExist:
                pass

        if openai_key:
            try:
                from openai import OpenAI
                client = OpenAI(api_key=openai_key)
                
                response = client.chat.completions.create(
                    model="gpt-4-turbo",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ]
                )
                ai_response = response.choices[0].message.content
            except Exception as e:
                ai_response = f"AI Error: {str(e)}"
        else:
            ai_response = f"Echo: {user_message} (No API key)"

        return JsonResponse({
            'status': 'success',
            'response': ai_response,
            'original_message': user_message
        })

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        })
