
from ..models import Tag
import os
from django.http import HttpResponse
from django.shortcuts import render,redirect
from ..models import User
from ..models import Message
from django.db.models import Max, Q
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

class Inboxcontroller:
    def dashboard(request):
        # 1. Initialize variables from Request FIRST
        selected_user_id = request.GET.get('user_id')
        tag_id = request.GET.get('tag_id')
        search_query = request.GET.get('search')

        # 2. Get organization/admin from session
        org_id = request.session.get("organization_id")
        admin_id = request.session.get("admin_id")

        if org_id:
            # Get organization - filter users by organization only
            from ..models import Organization
            org = Organization.objects.filter(id=org_id).first()
            # Filter by organization_id only (Organization doesn't have admin_id)
            users = User.objects.filter(
                organization_id=org_id
            ).annotate(
                last_msg_time=Max('message__created_at')
            ).order_by('-last_msg_time', 'id')
        elif admin_id:
            users = User.objects.filter(admin_id=admin_id).annotate(
                last_msg_time=Max('message__created_at')
            ).order_by('-last_msg_time', 'id')
        else:
            return redirect("/login")

        # 4. Apply Tag Filter
        if tag_id:
            users = users.filter(usertag__tag_id=tag_id)

        if search_query:
            users = users.filter(Q(name__icontains=search_query) | Q(phone_no__icontains=search_query))

        # 5. Context Data - filter tags by org/admin too
        if org_id:
            all_tags = Tag.objects.filter(organization_id=org_id)
        elif admin_id:
            all_tags = Tag.objects.filter(admin_id=admin_id)
        else:
            all_tags = Tag.objects.none()
        selected_user = None
        messages = []

        if selected_user_id:
            selected_user = User.objects.filter(id=selected_user_id).first()
            messages = Message.objects.filter(user_id=selected_user_id).order_by('created_at', 'id')

        
        if request.GET.get('ajax'):
            return render(request, 'inbox/partials/user_list.html', {
                'users': users,
                'selected_user': selected_user
            })

        return render(request, 'inbox/dashboard.html', {
            'users': users,
            'selected_user': selected_user,
            'messages': messages,
            'all_tags': all_tags,
        })

    def get_new_messages(request):
        user_id = request.GET.get('user_id')
        last_id = request.GET.get('last_id', 0)
        
        if not user_id:
            return JsonResponse({'error': 'Missing user_id'}, status=400)
            
        new_msgs = Message.objects.filter(
            user_id=user_id, 
            id__gt=last_id
        ).order_by('id')
        
        data = []
        for m in new_msgs:
            data.append({
                'id': m.id,
                'messages': m.messages,
                'who': m.who,
                'created_at': m.created_at.isoformat()
            })
            
        return JsonResponse({'messages': data})

    @csrf_exempt
    def upload_media(request):
        if request.method == 'POST' and request.FILES.get('file'):
            f = request.FILES['file']
            # Save to specific folder
            path = default_storage.save(f'chat_uploads/{f.name}', ContentFile(f.read()))
            url = os.path.join(settings.MEDIA_URL, path).replace('\\', '/')
            
            # Determine type
            ftype = 'file'
            if f.content_type.startswith('image'):
                ftype = 'image'
            elif f.content_type.startswith('video'):
                ftype = 'video'
                
            return JsonResponse({'url': url, 'type': ftype})
        return JsonResponse({'error': 'No file provided'}, status=400)

    @csrf_exempt
    def delete_user(request, user_id):
        """Delete a user from inbox (with all messages)"""
        if request.method != 'POST':
            return JsonResponse({'error': 'POST required'}, status=405)
        
        org_id = request.session.get('organization_id')
        admin_id = request.session.get('admin_id')
        
        if not org_id and not admin_id:
            return JsonResponse({'error': 'Not authenticated'}, status=401)
        
        # Get user and verify ownership
        user = User.objects.filter(id=user_id).first()
        if not user:
            return JsonResponse({'error': 'User not found'}, status=404)
        
        # Security check: ensure user belongs to same org/admin
        if org_id and user.organization_id != org_id:
            return JsonResponse({'error': 'Permission denied'}, status=403)
        if admin_id and str(user.admin_id_id) != str(admin_id):
            return JsonResponse({'error': 'Permission denied'}, status=403)
        
        # Delete messages first, then user
        Message.objects.filter(user_id=user_id).delete()
        user.delete()
        
        return JsonResponse({'success': True, 'msg': 'Contact deleted'})

    @csrf_exempt
    def toggle_bot(request, user_id):
        """Toggle bot on/off for a specific user"""
        if request.method != 'POST':
            return JsonResponse({'error': 'POST required'}, status=405)
        
        org_id = request.session.get('organization_id')
        admin_id = request.session.get('admin_id')
        
        if not org_id and not admin_id:
            return JsonResponse({'error': 'Not authenticated'}, status=401)
        
        user = User.objects.filter(id=user_id).first()
        if not user:
            return JsonResponse({'error': 'User not found'}, status=404)
        
        # Security check
        if org_id and user.organization_id != org_id:
            return JsonResponse({'error': 'Permission denied'}, status=403)
        if admin_id and str(user.admin_id_id) != str(admin_id):
            return JsonResponse({'error': 'Permission denied'}, status=403)
        
        # Toggle bot_enabled field
        user.bot_enabled = not getattr(user, 'bot_enabled', True)
        user.save(update_fields=['bot_enabled'])
        
        status = 'ON' if user.bot_enabled else 'OFF'
        return JsonResponse({'success': True, 'bot_enabled': user.bot_enabled, 'msg': f'Bot {status}'})

    @csrf_exempt
    def list_assets(request):
        """List all image assets for the logged-in user's org/admin"""
        from ..models import ImageAsset
        
        org_id = request.session.get('organization_id')
        admin_id = request.session.get('admin_id')
        
        if org_id:
            assets = ImageAsset.objects.filter(organization_id=org_id)
        elif admin_id:
            assets = ImageAsset.objects.filter(admin_id=admin_id)
        else:
            return JsonResponse({'assets': []})
        
        asset_list = [{
            'id': a.id,
            'name': a.name,
            'url': a.image.url if a.image else ''
        } for a in assets]
        
        return JsonResponse({'assets': asset_list})
