"""
WebChat Admin Controller
Handles admin-side management of webchat sessions, users, and analytics.
Integrates with existing inbox dashboard.
"""
import json
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Count, Avg, Sum, Q
from django.utils import timezone
from datetime import timedelta

from ..models import (
    WebChatSession,
    WebChatMessage,
    WebChatWidget,
    WebChatAnalytics,
    User,
    ChatGPTPrompt
)


class WebChatAdminController:
    """
    Admin controller for managing webchat functionality.
    Provides dashboard views, session management, and analytics.
    """
    
    @staticmethod
    def dashboard(request):
        """
        WebChat admin dashboard view.
        Shows active sessions, recent chats, and statistics.
        """
        # Get org/admin from session
        org_id = request.session.get("organization_id")
        admin_id = request.session.get("admin_id")
        
        if not org_id and not admin_id:
            return redirect("/login")
        
        # Filter sessions by organization/admin
        sessions_query = WebChatSession.objects.all()
        
        if org_id:
            sessions_query = sessions_query.filter(organization_id=org_id)
        elif admin_id:
            sessions_query = sessions_query.filter(admin_id=admin_id)
        
        # Get filter parameters
        status_filter = request.GET.get('status')
        date_range = request.GET.get('date_range', '7')  # Default: last 7 days
        
        # Apply status filter
        if status_filter:
            sessions_query = sessions_query.filter(status=status_filter)
        
        # Apply date range filter
        try:
            days = int(date_range)
            since_date = timezone.now() - timedelta(days=days)
            sessions_query = sessions_query.filter(started_at__gte=since_date)
        except (ValueError, TypeError):
            pass
        
        # Get sessions with message count
        sessions = sessions_query.annotate(
            message_count_calc=Count('messages')
        ).order_by('-started_at')[:100]  # Limit to recent 100
        
        # Statistics
        total_sessions = sessions_query.count()
        active_sessions = sessions_query.filter(status='active').count()
        ended_sessions = sessions_query.filter(status='ended').count()
        
        # Calculate average metrics
        analytics = WebChatAnalytics.objects.filter(session__in=sessions_query)
        avg_response_time = analytics.aggregate(avg=Avg('response_time_seconds'))['avg']
        avg_session_duration = analytics.aggregate(avg=Avg('session_duration_seconds'))['avg']
        
        # Message statistics
        total_messages = WebChatMessage.objects.filter(
            session__in=sessions_query
        ).count()
        
        # Feedback statistics
        feedback_stats = analytics.values('user_feedback').annotate(
            count=Count('id')
        )
        positive_count = sum(f['count'] for f in feedback_stats if f['user_feedback'] == 'positive')
        negative_count = sum(f['count'] for f in feedback_stats if f['user_feedback'] == 'negative')
        
        # Get widgets
        widgets_query = WebChatWidget.objects.filter(is_active=True)
        if org_id:
            widgets_query = widgets_query.filter(organization_id=org_id)
        elif admin_id:
            widgets_query = widgets_query.filter(admin_id=admin_id)
        widgets = widgets_query.order_by('-created_at')

        # Get ChatGPT prompts for the chat testing feature
        prompts_query = ChatGPTPrompt.objects.all()
        if org_id:
            prompts_query = prompts_query.filter(organization_id=org_id)
        elif admin_id:
            prompts_query = prompts_query.filter(Q(admin_id=admin_id) | Q(admin_id__isnull=True))
        prompts = prompts_query.order_by('-updated_at')[:20]

        # Get recent sessions for display
        recent_sessions = sessions_query.annotate(
            msg_count=Count('messages')
        ).order_by('-started_at')[:10]

        return render(request, 'webchat/dashboard.html', {
            'sessions': sessions,
            'recent_sessions': recent_sessions,
            'total_sessions': total_sessions,
            'active_sessions': active_sessions,
            'ended_sessions': ended_sessions,
            'total_messages': total_messages,
            'avg_response_time': round(avg_response_time, 2) if avg_response_time else 0,
            'avg_session_duration': round(avg_session_duration, 2) if avg_session_duration else 0,
            'positive_count': positive_count,
            'negative_count': negative_count,
            'widgets': widgets,
            'prompts': prompts,
            'current_status': status_filter,
            'current_date_range': date_range,
        })
    
    @staticmethod
    def session_detail(request, session_id):
        """
        View details of a specific webchat session.
        """
        org_id = request.session.get("organization_id")
        admin_id = request.session.get("admin_id")
        
        if not org_id and not admin_id:
            return redirect("/login")
        
        try:
            session = WebChatSession.objects.get(session_id=session_id)
            
            # Security check
            if org_id and session.organization_id != org_id:
                return redirect("/dashboard")
            if admin_id and session.admin_id != admin_id:
                return redirect("/dashboard")
            
            # Get messages
            messages = WebChatMessage.objects.filter(
                session=session
            ).order_by('created_at')
            
            # Get analytics
            analytics = WebChatAnalytics.objects.filter(session=session).first()
            
            return render(request, 'webchat/session_detail.html', {
                'session': session,
                'messages': messages,
                'analytics': analytics,
            })
            
        except WebChatSession.DoesNotExist:
            return redirect("/webchat/dashboard")

    @staticmethod
    @csrf_exempt
    def end_session_api(request):
        """
        API to end a webchat session manually.
        """
        if request.method != 'POST':
            return JsonResponse({'error': 'POST required'}, status=405)
        
        org_id = request.session.get("organization_id")
        admin_id = request.session.get("admin_id")
        
        if not org_id and not admin_id:
            return JsonResponse({'error': 'Not authenticated'}, status=401)
        
        try:
            data = json.loads(request.body)
            session_id = data.get('session_id')
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        
        if not session_id:
            return JsonResponse({'error': 'Missing session_id'}, status=400)
        
        try:
            session = WebChatSession.objects.get(session_id=session_id)
            
            # Security check
            if org_id and session.organization_id != org_id:
                return JsonResponse({'error': 'Permission denied'}, status=403)
            if admin_id and session.admin_id != admin_id:
                return JsonResponse({'error': 'Permission denied'}, status=403)
            
            # End session
            session.status = 'ended'
            session.ended_at = timezone.now()
            session.save(update_fields=['status', 'ended_at'])
            
            return JsonResponse({
                'success': True,
                'message': 'Session ended successfully'
            })
            
        except WebChatSession.DoesNotExist:
            return JsonResponse({'error': 'Session not found'}, status=404)
    
    @staticmethod
    @csrf_exempt
    def delete_session_api(request):
        """
        API to delete (archive) a webchat session.
        """
        if request.method != 'POST':
            return JsonResponse({'error': 'POST required'}, status=405)
        
        org_id = request.session.get("organization_id")
        admin_id = request.session.get("admin_id")
        
        if not org_id and not admin_id:
            return JsonResponse({'error': 'Not authenticated'}, status=401)
        
        try:
            data = json.loads(request.body)
            session_id = data.get('session_id')
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        
        if not session_id:
            return JsonResponse({'error': 'Missing session_id'}, status=400)
        
        try:
            session = WebChatSession.objects.get(session_id=session_id)
            
            # Security check
            if org_id and session.organization_id != org_id:
                return JsonResponse({'error': 'Permission denied'}, status=403)
            if admin_id and session.admin_id != admin_id:
                return JsonResponse({'error': 'Permission denied'}, status=403)
            
            # Delete session and all related messages
            session.delete()
            
            return JsonResponse({
                'success': True,
                'message': 'Session deleted successfully'
            })
            
        except WebChatSession.DoesNotExist:
            return JsonResponse({'error': 'Session not found'}, status=404)
    
    @staticmethod
    def analytics(request):
        """
        WebChat analytics view with detailed metrics.
        """
        org_id = request.session.get("organization_id")
        admin_id = request.session.get("admin_id")
        
        if not org_id and not admin_id:
            return redirect("/login")
        
        # Filter sessions
        sessions_query = WebChatSession.objects.all()
        if org_id:
            sessions_query = sessions_query.filter(organization_id=org_id)
        elif admin_id:
            sessions_query = sessions_query.filter(admin_id=admin_id)
        
        # Date range filter
        date_range = request.GET.get('date_range', '30')
        try:
            days = int(date_range)
            since_date = timezone.now() - timedelta(days=days)
            sessions_query = sessions_query.filter(started_at__gte=since_date)
        except (ValueError, TypeError):
            since_date = timezone.now() - timedelta(days=30)
            sessions_query = sessions_query.filter(started_at__gte=since_date)
        
        # Get analytics data
        analytics = WebChatAnalytics.objects.filter(session__in=sessions_query)
        
        # Summary stats
        summary = {
            'total_sessions': sessions_query.count(),
            'active_sessions': sessions_query.filter(status='active').count(),
            'ended_sessions': sessions_query.filter(status='ended').count(),
            'total_messages': WebChatMessage.objects.filter(session__in=sessions_query).count(),
            'avg_response_time': analytics.aggregate(avg=Avg('response_time_seconds'))['avg'],
            'avg_session_duration': analytics.aggregate(avg=Avg('session_duration_seconds'))['avg'],
            'total_escalations': analytics.filter(was_escalated=True).count(),
        }
        
        # Feedback breakdown
        feedback_data = analytics.values('user_feedback').annotate(
            count=Count('id')
        )
        feedback_summary = {f['user_feedback'] or 'none': f['count'] for f in feedback_data}
        
        # Sessions by day (for charts)
        from django.db.models.functions import TruncDate
        daily_sessions = sessions_query.annotate(
            date=TruncDate('started_at')
        ).values('date').annotate(
            count=Count('id')
        ).order_by('date')
        
        # Language distribution
        language_stats = sessions_query.values('language').annotate(
count=Count('id')
        )
        
        return render(request, 'webchat/analytics.html', {
            'summary': summary,
            'feedback_summary': feedback_summary,
            'daily_sessions': list(daily_sessions),
            'language_stats': list(language_stats),
            'date_range': date_range,
        })
    
    @staticmethod
    def widgets(request):
        """
        WebChat widget configuration view.
        """
        org_id = request.session.get("organization_id")
        admin_id = request.session.get("admin_id")
        
        if not org_id and not admin_id:
            return redirect("/login")
        
        # Get widgets
        widgets_query = WebChatWidget.objects.all()
        if org_id:
            widgets_query = widgets_query.filter(organization_id=org_id)
        elif admin_id:
            widgets_query = widgets_query.filter(admin_id=admin_id)
        
        widgets = widgets_query.order_by('-created_at')
        
        return render(request, 'webchat/widgets.html', {
            'widgets': widgets,
        })
    
    @staticmethod
    @csrf_exempt
    def create_widget(request):
        """
        API to create a new webchat widget configuration.
        """
        if request.method != 'POST':
            return JsonResponse({'error': 'POST required'}, status=405)
        
        org_id = request.session.get("organization_id")
        admin_id = request.session.get("admin_id")
        
        if not org_id and not admin_id:
            return JsonResponse({'error': 'Not authenticated'}, status=401)
        
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        
        try:
            widget = WebChatWidget.objects.create(
                admin_id=admin_id,
                organization_id=org_id,
                name=data.get('name', 'New Widget'),
                website_url=data.get('website_url'),
                display_mode=data.get('display_mode', 'button'),
                theme=data.get('theme', 'light'),
                primary_color=data.get('primary_color', '#007bff'),
                secondary_color=data.get('secondary_color', '#6c757d'),
                welcome_en=data.get('welcome_en', 'Welcome! How can we help you today?'),
                welcome_ar=data.get('welcome_ar', 'مرحبا! كيف يمكننا مساعدتك اليوم؟'),
                show_language_selector=data.get('show_language_selector', True),
                file_uploads_enabled=data.get('file_uploads_enabled', True),
                voice_input_enabled=data.get('voice_input_enabled', True),
                is_active=True
            )
            
            return JsonResponse({
                'success': True,
                'widget_id': widget.id,
                'message': 'Widget created successfully'
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    @staticmethod
    @csrf_exempt
    def update_widget(request, widget_id):
        """
        API to update a webchat widget configuration.
        """
        if request.method != 'POST':
            return JsonResponse({'error': 'POST required'}, status=405)
        
        org_id = request.session.get("organization_id")
        admin_id = request.session.get("admin_id")
        
        if not org_id and not admin_id:
            return JsonResponse({'error': 'Not authenticated'}, status=401)
        
        try:
            widget = WebChatWidget.objects.get(id=widget_id)
            
            # Security check
            if org_id and widget.organization_id != org_id:
                return JsonResponse({'error': 'Permission denied'}, status=403)
            if admin_id and widget.admin_id != admin_id:
                return JsonResponse({'error': 'Permission denied'}, status=403)
            
            try:
                data = json.loads(request.body)
            except json.JSONDecodeError:
                return JsonResponse({'error': 'Invalid JSON'}, status=400)
            
            # Update fields
            updatable_fields = [
                'name', 'website_url', 'display_mode', 'theme',
                'primary_color', 'secondary_color', 'text_color', 'background_color',
                'welcome_en', 'welcome_ar', 'show_language_selector',
                'file_uploads_enabled', 'voice_input_enabled', 'is_active'
            ]
            
            for field in updatable_fields:
                if field in data:
                    setattr(widget, field, data[field])
            
            widget.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Widget updated successfully'
            })
            
        except WebChatWidget.DoesNotExist:
            return JsonResponse({'error': 'Widget not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    @staticmethod
    @csrf_exempt
    def delete_widget(request, widget_id):
        """
        API to delete a webchat widget.
        """
        if request.method != 'POST':
            return JsonResponse({'error': 'POST required'}, status=405)
        
        org_id = request.session.get("organization_id")
        admin_id = request.session.get("admin_id")
        
        if not org_id and not admin_id:
            return JsonResponse({'error': 'Not authenticated'}, status=401)
        
        try:
            widget = WebChatWidget.objects.get(id=widget_id)
            
            # Security check
            if org_id and widget.organization_id != org_id:
                return JsonResponse({'error': 'Permission denied'}, status=403)
            if admin_id and widget.admin_id != admin_id:
                return JsonResponse({'error': 'Permission denied'}, status=403)
            
            widget.delete()
            
            return JsonResponse({
                'success': True,
                'message': 'Widget deleted successfully'
            })
            
        except WebChatWidget.DoesNotExist:
            return JsonResponse({'error': 'Widget not found'}, status=404)
    
    @staticmethod
    def get_widget_embed_code(request, widget_id):
        """
        Get the embed code for a webchat widget.
        """
        org_id = request.session.get("organization_id")
        admin_id = request.session.get("admin_id")
        
        if not org_id and not admin_id:
            return redirect("/login")
        
        try:
            widget = WebChatWidget.objects.get(id=widget_id)
            
            # Security check
            if org_id and widget.organization_id != org_id:
                return JsonResponse({'error': 'Permission denied'}, status=403)
            if admin_id and widget.admin_id != admin_id:
                return JsonResponse({'error': 'Permission denied'}, status=403)
            
            # Generate embed code
            embed_code = f'''<!-- WebChat Widget -->
<script>
(function() {{
    window.WebChatConfig = {{
        widgetId: {widget.id},
        apiUrl: '{request.build_absolute_uri('/api/webchat/').rstrip('/')}',
        theme: '{widget.theme}',
        primaryColor: '{widget.primary_color}'
    }};
}})();
</script>
<script src="{request.build_absolute_uri('/static/webchat/widget.js').rstrip('/')}" async></script>
<!-- End WebChat Widget -->'''
            
            return JsonResponse({
                'success': True,
                'embed_code': embed_code,
                'widget': {
                    'id': widget.id,
                    'name': widget.name,
                    'website_url': widget.website_url,
                }
            })
            
        except WebChatWidget.DoesNotExist:
            return JsonResponse({'error': 'Widget not found'}, status=404)

    @staticmethod
    @csrf_exempt
    def list_sessions_api(request):
        """
        API to list webchat sessions for the current admin/org.
        Used by the dashboard sidebar to show past chats.
        """
        org_id = request.session.get("organization_id")
        admin_id = request.session.get("admin_id")
        
        if not org_id and not admin_id:
            return JsonResponse({'error': 'Not authenticated'}, status=401)
        
        sessions_query = WebChatSession.objects.all()
        if org_id:
            sessions_query = sessions_query.filter(organization_id=org_id)
        elif admin_id:
            sessions_query = sessions_query.filter(admin_id=admin_id)
        
        sessions = sessions_query.annotate(
            msg_count=Count('messages')
        ).order_by('-started_at')[:50]
        
        sessions_data = []
        for s in sessions:
            sessions_data.append({
                'id': s.id,
                'session_id': s.session_id,
                'visitor_name': s.visitor_name or 'Test Chat',
                'status': s.status,
                'message_count': s.msg_count,
                'started_at': s.started_at.strftime('%b %d, %H:%M'),
                'last_activity': s.last_activity.strftime('%b %d, %H:%M'),
            })
        
        return JsonResponse({
            'success': True,
            'sessions': sessions_data
        })

    @staticmethod
    @csrf_exempt
    def get_session_messages_api(request, session_id):
        """
        API to get all messages for a specific session.
        Used to load past chat history.
        """
        org_id = request.session.get("organization_id")
        admin_id = request.session.get("admin_id")
        
        if not org_id and not admin_id:
            return JsonResponse({'error': 'Not authenticated'}, status=401)
        
        try:
            session = WebChatSession.objects.get(session_id=session_id)
            
            # Security check
            if org_id and session.organization_id != org_id:
                return JsonResponse({'error': 'Permission denied'}, status=403)
            if admin_id and session.admin_id != admin_id:
                return JsonResponse({'error': 'Permission denied'}, status=403)
            
            messages_list = WebChatMessage.objects.filter(
                session=session
            ).order_by('created_at')
            
            messages_data = []
            for m in messages_list:
                msg_entry = {
                    'id': m.id,
                    'content': m.content,
                    'sender': m.sender,
                    'content_type': m.content_type,
                    'created_at': m.created_at.strftime('%H:%M'),
                }
                if m.ai_response:
                    msg_entry['ai_response'] = m.ai_response
                messages_data.append(msg_entry)
            
            return JsonResponse({
                'success': True,
                'session_id': session_id,
                'visitor_name': session.visitor_name or 'Test Chat',
                'messages': messages_data
            })
            
        except WebChatSession.DoesNotExist:
            return JsonResponse({'error': 'Session not found'}, status=404)


# ==================== STANDALONE WEBCHAT PAGE ====================

def webchat_standalone_page(request, widget_id):
    """
    Public standalone webchat page — no auth required.
    Renders a full-page chat UI for a specific widget.
    Shareable link: /webchat/w/<widget_id>/
    """
    from ..models import Organization, Admin as AdminModel

    try:
        widget = WebChatWidget.objects.get(id=widget_id, is_active=True)
    except WebChatWidget.DoesNotExist:
        from django.http import Http404
        raise Http404("Chat widget not found or inactive.")

    # Get org/admin info for the widget
    org = None
    admin_obj = None
    org_name = 'Chat'
    if widget.organization_id:
        org = Organization.objects.filter(id=widget.organization_id).first()
        if org:
            org_name = org.name
    if widget.admin_id:
        admin_obj = AdminModel.objects.filter(id=widget.admin_id).first()
        if admin_obj and not org:
            org_name = admin_obj.assistant_name or 'Chat'

    # Build API base URL (protocol + host without trailing slash)
    api_base = request.build_absolute_uri('/').rstrip('/')

    return render(request, 'webchat/standalone.html', {
        'widget': widget,
        'org_name': org_name,
        'org_name_initial': org_name[0].upper() if org_name else 'C',
        'org_id': widget.organization_id or '',
        'admin_id': widget.admin_id or '',
        'api_base': api_base,
    })


# Convenience function for URL patterns
dashboard = WebChatAdminController.dashboard
session_detail = WebChatAdminController.session_detail
end_session_api = WebChatAdminController.end_session_api
delete_session_api = WebChatAdminController.delete_session_api
analytics = WebChatAdminController.analytics
widgets = WebChatAdminController.widgets
create_widget = WebChatAdminController.create_widget
update_widget = WebChatAdminController.update_widget
delete_widget = WebChatAdminController.delete_widget
get_widget_embed_code = WebChatAdminController.get_widget_embed_code
list_sessions_api = WebChatAdminController.list_sessions_api
get_session_messages_api = WebChatAdminController.get_session_messages_api

