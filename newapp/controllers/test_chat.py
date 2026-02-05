from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import json
from newapp.models import WebChatSession, WebChatMessage, WebChatWidget, ChatGPTPrompt
from newapp.views import chatgpt_respond
from newapp.controllers.inbox import Inboxcontroller
import uuid
from django.db.models import Count


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
    This is a lightweight test mode - doesn't save to database.
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
        system_prompt = ""
        if prompt_id:
            try:
                prompt = ChatGPTPrompt.objects.get(id=prompt_id)
                system_prompt = prompt.prompt_text or ""
            except ChatGPTPrompt.DoesNotExist:
                pass

        # Get AI response using existing chatgpt_respond function
        try:
            ai_response = chatgpt_respond(
                user_message=user_message,
                admin_id=request.session.get('admin_id'),
                custom_field_values=None,
                organization_id=request.session.get('organization_id'),
                system_prompt=system_prompt
            )
        except Exception as e:
            # Fallback response if AI fails
            ai_response = f"Test Mode: You said '{user_message}'. (AI response unavailable: {str(e)})"

        # Return response without saving to database (test mode)
        from datetime import datetime
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
        prompt_id = data.get('prompt_id', None)

        if not user_message:
            return JsonResponse({
                'status': 'error',
                'message': 'Please enter a message'
            })

        # Get the prompt if selected
        system_prompt = ""
        if prompt_id:
            try:
                prompt = ChatGPTPrompt.objects.get(id=prompt_id, is_active=True)
                system_prompt = prompt.system_prompt or ""
            except ChatGPTPrompt.DoesNotExist:
                pass

        # Try to get AI response
        try:
            ai_response = chatgpt_respond(
                user_message=user_message,
                admin_id=request.session.get('admin_id'),
                custom_field_values=None,
                organization_id=request.session.get('organization_id'),
                system_prompt=system_prompt
            )
        except Exception as e:
            # Fallback response
            ai_response = f"Test Response: I received your message: '{user_message}'"

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
