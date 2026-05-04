from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
import json
import re
import uuid
from newapp.models import ChatGPTPrompt, Admin, Organization, WebChatSession, WebChatMessage, User, Message
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
            text_parts = []
            # Handle {"messages": [...]}
            messages = data_json.get("messages", []) if isinstance(data_json, dict) else data_json if isinstance(data_json, list) else []
            if messages and isinstance(messages, list):
                for msg_item in messages:
                    if isinstance(msg_item, dict):
                        t = msg_item.get("text")
                        if not t:
                            t = msg_item.get("message", {}).get("text", "")
                        if t and isinstance(t, str) and t.strip():
                            text_parts.append(t.strip())
            # Handle {"text": "..."}
            if not text_parts and isinstance(data_json, dict) and "text" in data_json:
                t = data_json["text"]
                if t and isinstance(t, str) and t.strip():
                    text_parts.append(t.strip())
            if text_parts:
                clean_text = "\n\n".join(text_parts)
        except (json.JSONDecodeError, AttributeError, TypeError):
            # Try regex fallback — extract all "text" values from malformed JSON
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

    # --- Normalize escaped newlines (\\n -> real newline) ---
    clean_text = clean_text.replace('\\n', '\n')
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

        session_id_str = data.get('session_id', None)
        chat_session = None
        try:
            if session_id_str:
                chat_session = WebChatSession.objects.filter(session_id=session_id_str).first()

            if not chat_session:
                session_id_str = f"test_{uuid.uuid4().hex[:12]}"
                chat_session = WebChatSession.objects.create(
                    session_id=session_id_str,
                    visitor_name='Test Chat',
                    status='active',
                    admin_id=admin_id,
                    organization_id=org_id,
                )

            if (org_id or admin_id) and not chat_session.user_id:
                test_phone = f"webchat_test_{chat_session.session_id[:16]}"
                user_lookup = {'phone_no': test_phone}
                user_defaults = {
                    'name': 'Test Chat User',
                    'created_at': timezone.now(),
                    'source': 'Webchat Test',
                    'bot_enabled': True,
                    'is_in_inbox': True,
                }
                if org_id:
                    user_lookup['organization_id'] = org_id
                    user_defaults['organization_id'] = org_id
                if admin_id:
                    user_lookup['admin_id_id'] = admin_id
                    user_defaults['admin_id_id'] = admin_id

                test_user, _ = User.objects.get_or_create(
                    **user_lookup,
                    defaults=user_defaults
                )
                chat_session.user = test_user
                chat_session.save(update_fields=['user', 'last_activity'])
        except Exception as session_err:
            print(f"[TestChat] Session setup error: {session_err}")
        
        prompt_obj = None
        if prompt_id:
            prompt_qs = ChatGPTPrompt.objects.filter(id=prompt_id)
            if org_id:
                prompt_qs = prompt_qs.filter(organization_id=org_id)
            elif admin_id:
                prompt_qs = prompt_qs.filter(admin_id=admin_id)
            prompt_obj = prompt_qs.first()

        if not prompt_obj and org_id:
            prompt_obj = ChatGPTPrompt.objects.filter(organization_id=org_id, is_default=True).first()
            if not prompt_obj:
                prompt_obj = ChatGPTPrompt.objects.filter(organization_id=org_id).order_by('-updated_at').first()
        elif not prompt_obj and admin_id:
            prompt_obj = ChatGPTPrompt.objects.filter(admin_id=admin_id, is_default=True).first()
            if not prompt_obj:
                prompt_obj = ChatGPTPrompt.objects.filter(admin_id=admin_id).order_by('-updated_at').first()
        elif not prompt_obj:
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

                # Audio transcription: if content_type is 'audio', transcribe first
                content_type = data.get('content_type', 'text')
                ai_input_text = user_message
                if content_type == 'audio' and user_message:
                    try:
                        import requests as http_requests
                        from newapp.image_pdf_service import transcribe_audio_from_file
                        
                        audio_url = user_message
                        # Ensure we can reach the URL (use internal URL if needed)
                        if audio_url.startswith('http://chatbotad.io') or audio_url.startswith('https://chatbotad.io'):
                            # Try fetching internally
                            audio_resp = http_requests.get(audio_url, timeout=30, verify=False)
                        else:
                            audio_resp = http_requests.get(audio_url, timeout=30)
                        
                        if audio_resp.status_code == 200:
                            ext = 'webm'
                            if '.ogg' in audio_url: ext = 'ogg'
                            elif '.mp3' in audio_url: ext = 'mp3'
                            elif '.wav' in audio_url: ext = 'wav'
                            
                            transcription = transcribe_audio_from_file(
                                audio_resp.content, openai_key, file_ext=ext
                            )
                            if transcription:
                                ai_input_text = transcription
                            else:
                                ai_input_text = "[User sent a voice message that could not be transcribed]"
                        else:
                            ai_input_text = "[User sent a voice message]"
                    except Exception as audio_err:
                        print(f"[TestChat] Audio transcription error: {audio_err}")
                        ai_input_text = "[User sent a voice message]"

                # Build conversation history from existing session
                openai_messages = [{"role": "system", "content": system_prompt}]

                if chat_session:
                    past_msgs = WebChatMessage.objects.filter(
                        session=chat_session
                    ).order_by('created_at')
                    for m in past_msgs:
                        role = 'user' if m.sender == 'user' else 'assistant'
                        openai_messages.append({"role": role, "content": m.content})

                # Append the current user message (transcribed if audio)
                openai_messages.append({"role": "user", "content": ai_input_text})
                
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
        _booking_test_user = None  # Will be linked to session after persist
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
                    
                    # Create or reuse the linked test user so /book/<token>/ works.
                    try:
                        test_user = chat_session.user if chat_session and chat_session.user_id else None
                        if not test_user:
                            test_phone = f"webchat_test_{uuid.uuid4().hex[:8]}"
                            test_user = UserModel.objects.create(
                                phone_no=test_phone,
                                name='Test Chat User',
                                admin_id=admin_obj,
                                organization=org_obj,
                                source='Webchat Test',
                                bot_enabled=True,
                                is_in_inbox=True,
                                created_at=timezone.now(),
                            )
                        _booking_test_user = test_user
                        CalendlyBookingTracker.objects.create(
                            user=test_user,
                            calendly_link=link,
                            booking_token=booking_token,
                            status='link_sent'
                        )
                    except Exception as tracker_err:
                        _booking_test_user = None
                        print(f"[TestChat] Error creating booking tracker: {tracker_err}")
                else:
                    clean_text = clean_text.replace(full_tag, f"[Calendly link '{cal_name}' not found]")
        except Exception:
            pass

        # --- Persist to DB ---
        try:
            if not chat_session:
                session_id_str = f"test_{uuid.uuid4().hex[:12]}"
                chat_session = WebChatSession.objects.create(
                    session_id=session_id_str,
                    visitor_name='Test Chat',
                    status='active',
                    admin_id=admin_id,
                    organization_id=org_id,
                )

            if chat_session.user:
                try:
                    from newapp.models import Tag, UserTag, CustomField, CustomFieldValue
                    for tag_name in parsed['tags']:
                        tag_name = (tag_name or '').strip()
                        if not tag_name:
                            continue
                        tag_qs = Tag.objects.filter(
                            organization_id=org_id
                        ) if org_id else Tag.objects.filter(admin_id=admin_id)
                        tag = tag_qs.filter(name__iexact=tag_name).first()
                        if not tag:
                            create_kwargs = {'name': tag_name}
                            if org_id:
                                create_kwargs['organization_id'] = org_id
                            elif admin_id:
                                create_kwargs['admin_id'] = admin_id
                            tag = Tag.objects.create(**create_kwargs)
                        _, created = UserTag.objects.get_or_create(user=chat_session.user, tag=tag)
                        if created:
                            try:
                                from newapp.controllers.pipeline import run_pipeline_automations
                                run_pipeline_automations(chat_session.user.id, 'tag_applied', tag_id=tag.id)
                            except Exception:
                                pass

                    for field in parsed['custom_fields']:
                        field_name = (field.get('name') or '').strip()
                        field_value = field.get('value') or ''
                        if not field_name:
                            continue
                        field_qs = CustomField.objects.filter(
                            organization_id=org_id
                        ) if org_id else CustomField.objects.filter(admin_id=admin_id)
                        custom_field = field_qs.filter(name__iexact=field_name, is_active=True).first()
                        if custom_field:
                            CustomFieldValue.objects.update_or_create(
                                custom_field=custom_field,
                                user=chat_session.user,
                                defaults={'value': field_value}
                            )
                            try:
                                from newapp.controllers.pipeline import run_pipeline_automations
                                run_pipeline_automations(
                                    chat_session.user.id,
                                    'custom_field_changed',
                                    field_name=field_name,
                                    field_value=str(field_value)
                                )
                            except Exception:
                                pass
                except Exception as meta_err:
                    print(f"[TestChat] Metadata persistence error: {meta_err}")
            
            # Save user message
            WebChatMessage.objects.create(
                session=chat_session,
                content=user_message,
                sender='user',
                content_type='text',
            )
            if chat_session.user:
                Message.objects.create(
                    user_id=chat_session.user,
                    messages=user_message,
                    created_at=timezone.now(),
                    who='human'
                )
            
            # Save bot message (with tags/custom_fields in ai_response for persistence)
            bot_meta = {}
            if parsed['tags']:
                bot_meta['tags'] = parsed['tags']
            if parsed['custom_fields']:
                bot_meta['custom_fields'] = parsed['custom_fields']
            WebChatMessage.objects.create(
                session=chat_session,
                content=clean_text,
                sender='bot',
                content_type='text',
                ai_response=json.dumps(bot_meta) if bot_meta else None,
            )
            if chat_session.user:
                Message.objects.create(
                    user_id=chat_session.user,
                    messages=clean_text,
                    created_at=timezone.now(),
                    who='bot'
                )
            
            # Update message count
            chat_session.message_count = WebChatMessage.objects.filter(session=chat_session).count()
            chat_session.save(update_fields=['message_count', 'last_activity'])
            
            # Link booking test user to this session for confirmation messages
            if _booking_test_user and not chat_session.user_id:
                chat_session.user = _booking_test_user
                chat_session.save(update_fields=['user'])
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
