import uuid
import json
import logging
from django_ratelimit.decorators import ratelimit
from django.utils import timezone
from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from ..models import (
    WebChatSession, 
    WebChatMessage, 
    WebChatWidget,
    WebChatAnalytics,
    User,
    Admin,
    Organization
)
import re

logger = logging.getLogger(__name__)


class WebChatController:
    """
    Controller for handling web chat operations.
    Manages sessions, messages, and integrates with existing AI system.
    """
    
    def __init__(self, request=None):
        self.request = request
    
    @staticmethod
    def generate_session_id():
        """Generate a unique session ID for web chat."""
        return str(uuid.uuid4())
    
    @staticmethod
    def generate_anonymous_id():
        """Generate a temporary ID for anonymous users."""
        return f"anon_{uuid.uuid4().hex[:16]}"
    
    @classmethod
    def start_session(cls, request_data, admin_id=None, organization_id=None):
        """
        Start a new web chat session.
        
        Args:
            request_data: dict containing visitor info
            admin_id: Admin ID for the session
            organization_id: Organization ID for multi-tenant support
            
        Returns:
            dict with session info or error
        """
        try:
            # Get or create widget configuration
            widget = None
            if organization_id:
                widget = WebChatWidget.objects.filter(
                    organization_id=organization_id,
                    is_active=True
                ).first()
            elif admin_id:
                widget = WebChatWidget.objects.filter(
                    admin_id=admin_id,
                    is_active=True
                ).first()
            
            if not widget:
                # Use default widget settings
                widget = cls._get_default_widget(admin_id, organization_id)
            
            # Generate session ID
            session_id = cls.generate_session_id()
            anonymous_id = cls.generate_anonymous_id()
            
            # Determine language
            language = request_data.get('language', 'en')
            if language not in ['en', 'ar', 'both']:
                language = 'en'
            
            # Create or link a User record so tags/APIs/bookings work
            webchat_phone = f"webchat_{session_id[:16]}"
            visitor_name = request_data.get('visitor_name', '')
            visitor_email = request_data.get('visitor_email', '')
            try:
                user_obj, _ = User.objects.get_or_create(
                    phone_no=webchat_phone,
                    defaults={
                        'name': visitor_name or f'Webchat {anonymous_id[:8]}',
                        'admin_id': admin_id,
                        'organization_id': organization_id,
                        'created_at': timezone.now(),
                    }
                )
                if visitor_name and user_obj.name != visitor_name:
                    user_obj.name = visitor_name
                    user_obj.save(update_fields=['name'])
            except Exception as user_err:
                logger.error(f"Error creating webchat user: {user_err}")
                user_obj = None
            
            # Create session
            session = WebChatSession.objects.create(
                session_id=session_id,
                anonymous_id=anonymous_id,
                user=user_obj,
                admin_id=admin_id,
                organization_id=organization_id,
                language=language,
                visitor_name=visitor_name,
                visitor_email=visitor_email,
                ip_address=request_data.get('ip_address'),
                user_agent=request_data.get('user_agent'),
                status='active'
            )
            
            # Get welcome message based on language
            if language == 'ar':
                welcome_text = widget.welcome_ar if widget else "مرحبا! كيف يمكننا مساعدتك اليوم؟"
            elif language == 'both':
                welcome_text = f"""Welcome! How can we help you today?
مرحبا! كيف يمكننا مساعدتك اليوم؟"""
            else:
                welcome_text = widget.welcome_en if widget else "Welcome! How can we help you today?"
            
            # Send welcome message
            welcome_message = WebChatMessage.objects.create(
session=session,
                content=welcome_text,
                sender='bot',
                content_type='text'
            )
            
            # Create analytics entry
            WebChatAnalytics.objects.create(
                session=session,
                message_count=1
            )
            
            return {
                'success': True,
                'session': {
                    'id': session.session_id,
                    'language': session.language,
                    'started_at': session.started_at.isoformat(),
                },
                'welcome_message': {
                    'id': welcome_message.id,
                    'content': welcome_message.content,
                    'sender': welcome_message.sender,
                    'created_at': welcome_message.created_at.isoformat(),
                },
                'widget': {
                    'show_language_selector': widget.show_language_selector if widget else True,
                    'file_uploads_enabled': widget.file_uploads_enabled if widget else True,
                    'voice_input_enabled': widget.voice_input_enabled if widget else True,
                } if widget else None
            }
            
        except Exception as e:
            logger.error(f"Error starting webchat session: {str(e)}")
            return {
                'success': False,
                'error': 'Failed to start session'
            }
    
    @classmethod
    def _get_default_widget(cls, admin_id=None, organization_id=None):
        """Get or create default widget configuration."""
        try:
            widget = WebChatWidget.objects.filter(
                admin_id=admin_id,
                organization_id=organization_id,
                is_active=True
            ).first()
            
            if not widget:
                # Create default widget if none exists
                widget = WebChatWidget.objects.create(
                    admin_id=admin_id,
                    organization_id=organization_id,
                    name='Default Web Chat',
                    welcome_en='Welcome! How can we help you today?',
                    welcome_ar='مرحبا! كيف يمكننا مساعدتك اليوم؟',
                    show_language_selector=True,
                    file_uploads_enabled=True,
                    voice_input_enabled=True,
                    is_active=True
                )
            
            return widget
        except Exception as e:
            logger.error(f"Error getting default widget: {str(e)}")
            return None
    
    @classmethod
    def send_message(cls, request_data):
        """
        Handle sending a message in a web chat session.
        
        Args:
            request_data: dict containing session_id, message, etc.
            
        Returns:
            dict with bot response or error
        """
        try:
            session_id = request_data.get('session_id')
            message_content = request_data.get('message', '').strip()
            content_type = request_data.get('content_type', 'text')
            
            if not session_id:
                return {
                    'success': False,
                    'error': 'Session ID is required'
                }
            
            if not message_content and content_type == 'text':
                return {
                    'success': False,
                    'error': 'Message content is required'
                }
            
            # Get session
            try:
                session = WebChatSession.objects.get(session_id=session_id)
            except WebChatSession.DoesNotExist:
                return {
                    'success': False,
                    'error': 'Session not found'
                }
            
            if session.status != 'active':
                return {
                    'success': False,
                    'error': 'Session is not active'
                }
            
            # Update session activity
            session.last_activity = timezone.now()
            session.message_count += 1
            session.save(update_fields=['last_activity', 'message_count'])
            
            # Create user message
            user_message = WebChatMessage.objects.create(
                session=session,
                content=message_content,
                sender='user',
                content_type=content_type
            )
            
            # Process message through AI system
            ai_response = None
            bot_response_text = None
            
            try:
                # Get system prompt — Feature 1: prefer is_default prompt
                from ..models import ChatGPTPrompt
                prompt_obj = None
                if session.organization_id:
                    prompt_obj = ChatGPTPrompt.objects.filter(
                        organization_id=session.organization_id, is_default=True
                    ).first()
                    if not prompt_obj:
                        prompt_obj = ChatGPTPrompt.objects.filter(
                            organization_id=session.organization_id
                        ).order_by('-updated_at').first()
                elif session.admin_id:
                    prompt_obj = ChatGPTPrompt.objects.filter(
                        admin_id=session.admin_id, is_default=True
                    ).first()
                    if not prompt_obj:
                        prompt_obj = ChatGPTPrompt.objects.filter(
                            admin_id=session.admin_id
                        ).order_by('-updated_at').first()
                
                system_prompt = (
                    prompt_obj.prompt_text.strip()
                    if prompt_obj and prompt_obj.prompt_text
                    else "You are a helpful assistant."
                )
                
                # Get OpenAI API key
                openai_key = None
                gpt_model = 'gpt-4o-mini'
                
                # Use per-prompt gpt_model if set
                if prompt_obj and prompt_obj.gpt_model:
                    gpt_model = prompt_obj.gpt_model
                
                if session.organization_id:
                    org_obj = Organization.objects.filter(id=session.organization_id).first()
                    if org_obj:
                        openai_key = org_obj.openai_api_key
                        if not gpt_model or gpt_model == 'gpt-4o-mini':
                            gpt_model = getattr(org_obj, 'gpt_model', gpt_model)
                
                if not openai_key and session.admin_id:
                    admin_obj_ai = Admin.objects.filter(id=session.admin_id).first()
                    if admin_obj_ai:
                        openai_key = admin_obj_ai.openai_api_key
                
                if openai_key:
                    from openai import OpenAI
                    client = OpenAI(api_key=openai_key)
                    
                    # Build conversation history from session messages
                    # Note: the current user message was already saved to DB above,
                    # so it is included in this query — no need to append it again.
                    messages_history = [{"role": "system", "content": system_prompt}]
                    past_messages = WebChatMessage.objects.filter(
                        session=session
                    ).order_by('-created_at')[:20]  # Last 20 messages for context
                    
                    for past_msg in reversed(list(past_messages)):
                        role = "user" if past_msg.sender == "user" else "assistant"
                        messages_history.append({
                            "role": role,
                            "content": past_msg.content or ""
                        })
                    
                    response = client.chat.completions.create(
                        model=gpt_model,
                        messages=messages_history
                    )
                    bot_response_text = response.choices[0].message.content
                    
                    # Extract clean text if AI returned JSON format
                    if bot_response_text:
                        stripped = bot_response_text.strip()
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
                                messages_list = data_json.get("messages", []) if isinstance(data_json, dict) else data_json if isinstance(data_json, list) else []
                                if messages_list and isinstance(messages_list, list):
                                    for msg_item in messages_list:
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
                                    bot_response_text = "\n\n".join(text_parts)
                            except (json.JSONDecodeError, AttributeError, TypeError):
                                # Try regex fallback
                                text_matches = re.findall(r'"text"\s*:\s*"((?:[^"\\]|\\.)*)"', stripped)
                                if text_matches:
                                    extracted = []
                                    for t in text_matches:
                                        t = t.replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')
                                        if t.strip():
                                            extracted.append(t.strip())
                                    if extracted:
                                        bot_response_text = "\n\n".join(extracted)
                        
                        # Normalize escaped newlines
                        bot_response_text = bot_response_text.replace('\\n', '\n')
                        bot_response_text = re.sub(r'\n\s*\n\s*\n', '\n\n', bot_response_text)
                else:
                    bot_response_text = "I'm sorry, the AI service is not configured yet. Please try again later."
                    
            except Exception as ai_error:
                logger.error(f"AI response error: {str(ai_error)}")
                bot_response_text = "Sorry, I'm having trouble connecting to the AI service. Please try again later."
            
            # Process {{image:name}} tags for webchat
            image_urls = []
            if bot_response_text:
                try:
                    from ..image_tag_processor import parse_image_tags, get_image_asset
                    from ..models import Admin as AdminModel, ImageAsset
                    
                    image_tags = parse_image_tags(bot_response_text)
                    if image_tags:
                        # Get admin/org for looking up assets
                        admin_obj = None
                        org_obj = None
                        if session.organization_id:
                            org_obj = Organization.objects.filter(id=session.organization_id).first()
                        if session.admin_id:
                            admin_obj = AdminModel.objects.filter(id=session.admin_id).first()
                        
                        for full_tag, image_name in image_tags:
                            asset = get_image_asset(image_name, admin_obj, org_obj)
                            if asset and asset.image:
                                image_urls.append({
                                    'name': image_name,
                                    'url': asset.image.url,
                                })
                        
                        # Remove image tags from text
                        bot_response_text = re.sub(r'\{\{image:[a-zA-Z0-9_]+\}\}', '', bot_response_text).strip()
                        # Clean up extra whitespace
                        bot_response_text = re.sub(r'\n\s*\n\s*\n', '\n\n', bot_response_text)
                except Exception as img_error:
                    logger.error(f"Image tag processing error: {str(img_error)}")
            
            # Process action tags ({{calendly:name}}, {{tag:...}}, {{api:...}}, {{gcalendar:...}})
            if bot_response_text:
                try:
                    from ..action_tag_processor import process_response_actions
                    # Resolve admin/org objects for the action tag processor
                    admin_obj = None
                    org_obj = None
                    webchat_phone = None
                    if session.admin_id:
                        admin_obj = Admin.objects.filter(id=session.admin_id).first()
                    if session.organization_id:
                        org_obj = Organization.objects.filter(id=session.organization_id).first()
                    if session.user:
                        webchat_phone = session.user.phone_no
                    else:
                        webchat_phone = f"webchat_{session.session_id[:16]}"
                    
                    tag_result = process_response_actions(
                        bot_response_text,
                        admin_obj,
                        webchat_phone,
                        org_obj
                    )
                    # process_response_actions returns a dict with 'final_text'
                    if isinstance(tag_result, dict):
                        bot_response_text = tag_result.get('final_text', bot_response_text)
                    elif isinstance(tag_result, str):
                        bot_response_text = tag_result
                except Exception as tag_error:
                    logger.error(f"Action tag processing error: {str(tag_error)}")
            
            # Strip any remaining metadata tags not meant for end users
            if bot_response_text:
                bot_response_text = re.sub(r'\{\{custom_field:[^}]*\}\}', '', bot_response_text)
                bot_response_text = re.sub(r'\{\{tag:(add|remove):[^}]*\}\}', '', bot_response_text)
                bot_response_text = re.sub(r'\n\s*\n\s*\n', '\n\n', bot_response_text).strip()

            # Create bot message
            bot_message = WebChatMessage.objects.create(
                session=session,
                content=bot_response_text,
                sender='bot',
                content_type='text',
                ai_response=ai_response if isinstance(ai_response, str) else json.dumps(ai_response) if ai_response else None
            )
            
            # Update analytics
            try:
                analytics = WebChatAnalytics.objects.get(session=session)
                analytics.message_count = session.message_count
                analytics.save(update_fields=['message_count'])
            except WebChatAnalytics.DoesNotExist:
                WebChatAnalytics.objects.create(
                    session=session,
                    message_count=session.message_count
                )
            
            return {
                'success': True,
                'user_message': {
                    'id': user_message.id,
                    'content': user_message.content,
                    'sender': user_message.sender,
                    'created_at': user_message.created_at.isoformat(),
                },
                'bot_message': {
                    'id': bot_message.id,
                    'content': bot_message.content,
                    'sender': bot_message.sender,
                    'created_at': bot_message.created_at.isoformat(),
                    'images': image_urls,
                }
            }
            
        except Exception as e:
            logger.error(f"Error sending webchat message: {str(e)}")
            return {
                'success': False,
                'error': 'Failed to process message'
            }
    
    @classmethod
    def get_messages(cls, session_id, since=None):
        """
        Get messages for a web chat session.
        
        Args:
            session_id: The session ID
            since: Optional timestamp to get messages after
            
        Returns:
            dict with messages list
        """
        try:
            session = WebChatSession.objects.get(session_id=session_id)
            
            messages = WebChatMessage.objects.filter(session=session)
            
            if since:
                since_dt = timezone.datetime.fromisoformat(since)
                messages = messages.filter(created_at__gt=since_dt)
            
            messages = messages.order_by('created_at')
            
            message_list = []
            for msg in messages:
                message_list.append({
                    'id': msg.id,
                    'content': msg.content,
                    'sender': msg.sender,
                    'content_type': msg.content_type,
                    'created_at': msg.created_at.isoformat(),
                })
            
            return {
                'success': True,
                'session': {
                    'id': session.session_id,
                    'status': session.status,
                    'message_count': session.message_count,
                },
                'messages': message_list
            }
            
        except WebChatSession.DoesNotExist:
            return {
                'success': False,
                'error': 'Session not found'
            }
        except Exception as e:
            logger.error(f"Error getting webchat messages: {str(e)}")
            return {
                'success': False,
                'error': 'Failed to get messages'
            }
    
    @classmethod
    def end_session(cls, session_id):
        """
        End a web chat session.
        
        Args:
            session_id: The session ID to end
            
        Returns:
            dict with success status
        """
        try:
            session = WebChatSession.objects.get(session_id=session_id)
            
            session.status = 'ended'
            session.ended_at = timezone.now()
            
            # Calculate duration
            if session.started_at:
                duration = (session.ended_at - session.started_at).total_seconds()
                session.save(update_fields=['status', 'ended_at'])
                
                # Update analytics with duration
                try:
                    analytics = WebChatAnalytics.objects.get(session=session)
                    analytics.session_duration_seconds = int(duration)
                    analytics.save(update_fields=['session_duration_seconds'])
                except WebChatAnalytics.DoesNotExist:
                    pass
            
            return {
                'success': True,
                'message': 'Session ended successfully',
                'ended_at': session.ended_at.isoformat()
            }
            
        except WebChatSession.DoesNotExist:
            return {
                'success': False,
                'error': 'Session not found'
            }
        except Exception as e:
            logger.error(f"Error ending webchat session: {str(e)}")
            return {
                'success': False,
                'error': 'Failed to end session'
            }
    
    @classmethod
    def set_user_feedback(cls, session_id, feedback):
        """
        Set user feedback for a session.
        
        Args:
            session_id: The session ID
            feedback: 'positive', 'neutral', or 'negative'
            
        Returns:
            dict with success status
        """
        try:
            if feedback not in ['positive', 'neutral', 'negative']:
                feedback = ''
            
            analytics = WebChatAnalytics.objects.get(session__session_id=session_id)
            analytics.user_feedback = feedback
            analytics.save(update_fields=['user_feedback'])
            
            return {
                'success': True,
                'message': 'Feedback recorded'
            }
            
        except WebChatAnalytics.DoesNotExist:
            return {
                'success': False,
                'error': 'Analytics not found for session'
            }
        except Exception as e:
            logger.error(f"Error setting feedback: {str(e)}")
            return {
                'success': False,
                'error': 'Failed to record feedback'
            }
    
    @classmethod
    def update_language(cls, session_id, language):
        """
        Update the language preference for a session.
        
        Args:
            session_id: The session ID
            language: 'en', 'ar', or 'both'
            
        Returns:
            dict with success status
        """
        try:
            if language not in ['en', 'ar', 'both']:
                return {
                    'success': False,
                    'error': 'Invalid language. Use en, ar, or both'
                }
            
            session = WebChatSession.objects.get(session_id=session_id)
            session.language = language
            session.save(update_fields=['language'])
            
            return {
                'success': True,
                'language': language
            }
            
        except WebChatSession.DoesNotExist:
            return {
                'success': False,
                'error': 'Session not found'
            }
        except Exception as e:
            logger.error(f"Error updating language: {str(e)}")
            return {
                'success': False,
                'error': 'Failed to update language'
            }


# Django view functions for API endpoints

@csrf_exempt
@require_http_methods(["POST"])
@ratelimit(key="ip", rate="50/h", block=True)
def api_webchat_start(request):
    """
    API endpoint to start a new web chat session.
    
    POST /api/webchat/start/
    Body: {
        "visitor_name": "optional",
        "visitor_email": "optional",
        "language": "en",
        "ip_address": "optional",
        "user_agent": "optional"
    }
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        data = {}
    
    # Get organization/admin from request if available
    admin_id = data.get('admin_id')
    organization_id = data.get('organization_id')
    
    result = WebChatController.start_session(
        request_data=data,
        admin_id=admin_id,
        organization_id=organization_id
    )
    
    return JsonResponse(result)


@csrf_exempt
@require_http_methods(["POST"])
@ratelimit(key="ip", rate="100/h", block=True)
def api_webchat_message(request):
    """
    API endpoint to send a message in a web chat session.
    
    POST /api/webchat/message/
    Body: {
        "session_id": "required",
        "message": "required",
        "content_type": "text"
    }
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON body'
        })
    
    result = WebChatController.send_message(request_data=data)
    
    return JsonResponse(result)


@csrf_exempt
@require_http_methods(["GET"])
@ratelimit(key="ip", rate="100/h", block=True)
def api_webchat_messages(request, session_id):
    """
    API endpoint to get messages for a web chat session.
    
    GET /api/webchat/messages/<session_id>/
    Query params: since (optional ISO timestamp)
    """
    since = request.GET.get('since')
    result = WebChatController.get_messages(session_id, since=since)
    
    return JsonResponse(result)


@csrf_exempt
@require_http_methods(["POST"])
@ratelimit(key="ip", rate="30/h", block=True)
def api_webchat_end(request):
    """
    API endpoint to end a web chat session.
    
    POST /api/webchat/end/
    Body: {
        "session_id": "required"
    }
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON body'
        })
    
    session_id = data.get('session_id')
    if not session_id:
        return JsonResponse({
            'success': False,
            'error': 'Session ID is required'
        })
    
    result = WebChatController.end_session(session_id)
    
    return JsonResponse(result)


@csrf_exempt
@require_http_methods(["POST"])
@ratelimit(key="ip", rate="20/h", block=True)
def api_webchat_feedback(request):
    """
    API endpoint to submit user feedback for a session.
    
    POST /api/webchat/feedback/
    Body: {
        "session_id": "required",
        "feedback": "positive|neutral|negative"
    }
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON body'
        })
    
    session_id = data.get('session_id')
    feedback = data.get('feedback', '')
    
    if not session_id:
        return JsonResponse({
            'success': False,
            'error': 'Session ID is required'
        })
    
    result = WebChatController.set_user_feedback(session_id, feedback)
    
    return JsonResponse(result)


@csrf_exempt
@require_http_methods(["POST"])
@ratelimit(key="ip", rate="20/h", block=True)
def api_webchat_language(request):
    """
    API endpoint to update language preference for a session.
    
    POST /api/webchat/language/
    Body: {
        "session_id": "required",
        "language": "en|ar|both"
    }
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON body'
        })
    
    session_id = data.get('session_id')
    language = data.get('language', 'en')
    
    if not session_id:
        return JsonResponse({
            'success': False,
            'error': 'Session ID is required'
        })
    
    result = WebChatController.update_language(session_id, language)
    
    return JsonResponse(result)
