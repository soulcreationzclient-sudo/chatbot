from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import json
import re
import uuid
from newapp.models import ChatGPTPrompt, Admin, Organization, WebChatSession, WebChatMessage
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

        # Feature 1: prefer is_default prompt, fallback to latest
        org_id = request.session.get('organization_id')
        admin_id = request.session.get('admin_id')
        
        if org_id:
            prompt_obj = ChatGPTPrompt.objects.filter(organization_id=org_id, is_default=True).first()
            if not prompt_obj:
                prompt_obj = ChatGPTPrompt.objects.filter(organization_id=org_id).order_by('-updated_at').first()
        elif admin_id:
            prompt_obj = ChatGPTPrompt.objects.filter(admin_id=admin_id, is_default=True).first()
            if not prompt_obj:
                prompt_obj = ChatGPTPrompt.objects.filter(admin_id=admin_id).order_by('-updated_at').first()
        else:
            prompt_obj = ChatGPTPrompt.objects.order_by('-updated_at').first()
        system_prompt = prompt_obj.prompt_text if prompt_obj else "You are a helpful assistant."

        # Get OpenAI API key from organization or admin
        openai_key = None
        gpt_model = 'gpt-4o-mini'
        
        # Use per-prompt gpt_model if set
        if prompt_obj and prompt_obj.gpt_model:
            gpt_model = prompt_obj.gpt_model
        
        if org_id:
            try:
                org = Organization.objects.get(id=org_id)
                openai_key = org.openai_api_key
                if not gpt_model or gpt_model == 'gpt-4o-mini':
                    gpt_model = getattr(org, 'gpt_model', gpt_model)
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

                # Build conversation history from existing session
                openai_messages = [{"role": "system", "content": system_prompt}]

                session_id_str = data.get('session_id', None)
                if session_id_str:
                    chat_session = WebChatSession.objects.filter(session_id=session_id_str).first()
                    if chat_session:
                        past_msgs = WebChatMessage.objects.filter(
                            session=chat_session
                        ).order_by('created_at')
                        for m in past_msgs:
                            role = 'user' if m.sender == 'user' else 'assistant'
                            openai_messages.append({"role": role, "content": m.content})

                # Append the current user message
                openai_messages.append({"role": "user", "content": user_message})
                
                response = client.chat.completions.create(
                    model=gpt_model,
                    messages=openai_messages
                )
                ai_response = response.choices[0].message.content
            except Exception as e:
                ai_response = f"AI Error: {str(e)}"
        else:
            ai_response = f"Test Mode: You said '{user_message}'. (No OpenAI API key configured)"

        # Parse the response to extract clean text, tags, and custom fields
        parsed = _parse_ai_response(ai_response)

        # Process {{image:name}} tags
        image_urls = []
        clean_text = parsed['clean_text']
        try:
            import re as re_mod
            from newapp.image_tag_processor import parse_image_tags, get_image_asset
            from newapp.models import Admin as AdminModel, Organization as OrgModel
            
            img_tags = parse_image_tags(clean_text)
            if img_tags:
                admin_obj = None
                org_obj = None
                if org_id:
                    org_obj = OrgModel.objects.filter(id=org_id).first()
                if admin_id:
                    admin_obj = AdminModel.objects.filter(id=admin_id).first()
                
                for full_tag, img_name in img_tags:
                    asset = get_image_asset(img_name, admin_obj, org_obj)
                    if asset and asset.image:
                        image_urls.append({
                            'name': img_name,
                            'url': asset.image.url,
                        })
                
                # Remove image tags from text
                clean_text = re_mod.sub(r'\{\{image:[a-zA-Z0-9_]+\}\}', '', clean_text).strip()
                clean_text = re_mod.sub(r'\n\s*\n\s*\n', '\n\n', clean_text)
        except Exception as img_err:
            pass  # Silently fail if image processing fails

        # Process {{calendly:name}} tags — replace with booking redirect URL
        try:
            import re as re_mod2
            from newapp.models import CalendlyLink, CalendlyBookingTracker, User as UserModel, Admin as AdminModel, Organization as OrgModel
            calendly_matches = list(re_mod2.finditer(r'\{\{calendly:([a-zA-Z0-9_\-\s]+)\}\}', clean_text))
            for match in calendly_matches:
                cal_name = match.group(1).strip()
                full_tag = match.group(0)
                link = None
                admin_obj = None
                org_obj = None
                if org_id:
                    org_obj = OrgModel.objects.filter(id=org_id).first()
                    if org_obj:
                        link = CalendlyLink.objects.filter(organization=org_obj, name__iexact=cal_name).first()
                if not link and admin_id:
                    admin_obj = AdminModel.objects.filter(id=admin_id).first()
                    if admin_obj:
                        link = CalendlyLink.objects.filter(admin=admin_obj, name__iexact=cal_name).first()
                
                if link:
                    booking_token = uuid.uuid4().hex[:16]
                    redirect_url = f"https://chatbotad.io/book/{booking_token}/"
                    clean_text = clean_text.replace(full_tag, redirect_url)
                    
                    # Create a test user and tracker record so /book/<token>/ works
                    try:
                        test_phone = f"test_{uuid.uuid4().hex[:8]}"
                        test_user, _ = UserModel.objects.get_or_create(
                            phone_no=test_phone,
                            defaults={
                                'name': 'Test Chat User',
                                'admin_id': admin_obj,
                                'organization': org_obj,
                            }
                        )
                        CalendlyBookingTracker.objects.create(
                            user=test_user,
                            calendly_link=link,
                            booking_token=booking_token,
                            status='link_sent'
                        )
                    except Exception:
                        pass
                else:
                    clean_text = clean_text.replace(full_tag, f"[Calendly link '{cal_name}' not found]")
        except Exception:
            pass

        # --- Persist to DB ---
        session_id_str = data.get('session_id', None)
        try:
            if session_id_str:
                chat_session = WebChatSession.objects.filter(session_id=session_id_str).first()
            else:
                chat_session = None
            
            if not chat_session:
                session_id_str = f"test_{uuid.uuid4().hex[:12]}"
                chat_session = WebChatSession.objects.create(
                    session_id=session_id_str,
                    visitor_name='Test Chat',
                    status='active',
                    admin_id=admin_id,
                    organization_id=org_id,
                )
            
            # Save user message
            WebChatMessage.objects.create(
                session=chat_session,
                content=user_message,
                sender='user',
                content_type='text',
            )
            
            # Save bot message
            WebChatMessage.objects.create(
                session=chat_session,
                content=clean_text,
                sender='bot',
                content_type='text',
            )
            
            # Update message count
            chat_session.message_count = WebChatMessage.objects.filter(session=chat_session).count()
            chat_session.save(update_fields=['message_count', 'last_activity'])
        except Exception:
            pass  # Don't break chat if DB save fails

        # Return response
        now = datetime.now().isoformat()
        
        return JsonResponse({
            'status': 'success',
            'session_id': session_id_str,
            'user_message': {
                'content': user_message,
                'created_at': now
            },
            'bot_message': {
                'content': clean_text,
                'raw_content': parsed['raw_response'],
                'tags': parsed['tags'],
                'custom_fields': parsed['custom_fields'],
                'images': image_urls,
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

        # Feature 1: prefer is_default prompt per org/admin
        org_id = request.session.get('organization_id')
        admin_id = request.session.get('admin_id')
        
        if org_id:
            prompt_obj = ChatGPTPrompt.objects.filter(organization_id=org_id, is_default=True).first()
            if not prompt_obj:
                prompt_obj = ChatGPTPrompt.objects.filter(organization_id=org_id).order_by('-updated_at').first()
        elif admin_id:
            prompt_obj = ChatGPTPrompt.objects.filter(admin_id=admin_id, is_default=True).first()
            if not prompt_obj:
                prompt_obj = ChatGPTPrompt.objects.filter(admin_id=admin_id).order_by('-updated_at').first()
        else:
            prompt_obj = ChatGPTPrompt.objects.order_by('-updated_at').first()
        system_prompt = prompt_obj.prompt_text if prompt_obj else "You are a helpful assistant."

        # Get OpenAI API key
        openai_key = None
        gpt_model = 'gpt-4o-mini'
        
        # Use per-prompt gpt_model if set
        if prompt_obj and prompt_obj.gpt_model:
            gpt_model = prompt_obj.gpt_model
        
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
