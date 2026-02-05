from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import json
from newapp.models import ChatGPTPrompt, Admin, Organization
from datetime import datetime


def test_chat(request):
    """
    Simple chat interface for testing prompts - redirects to dashboard with chat tab.
    """
    return redirect('/webchat/dashboard/?tab=test-chat')


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

        # Get the prompt if selected
        system_prompt = "You are a helpful assistant."
        if prompt_id:
            try:
                prompt = ChatGPTPrompt.objects.get(id=prompt_id)
                system_prompt = prompt.prompt_text or system_prompt
            except ChatGPTPrompt.DoesNotExist:
                pass
        else:
            # Get default prompt from database
            prompt_obj = ChatGPTPrompt.objects.order_by('-updated_at').first()
            if prompt_obj:
                system_prompt = prompt_obj.prompt_text or system_prompt

        # Get OpenAI API key from organization or admin
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

        # Call OpenAI if we have a key
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
            ai_response = f"Test Mode: You said '{user_message}'. (No OpenAI API key configured)"

        # Return response
        now = datetime.now().isoformat()
        
        return JsonResponse({
            'status': 'success',
            'user_message': {
                'content': user_message,
                'created_at': now
            },
            'bot_message': {
                'content': ai_response,
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
