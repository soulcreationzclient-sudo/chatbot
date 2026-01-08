
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

        # 3. Base Query - filter by organization or admin
        if org_id:
            users = User.objects.filter(organization_id=org_id).annotate(
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
            all_tags = Tag.objects.filter(organization_id=org_id) if hasattr(Tag, 'organization_id') else Tag.objects.all()
        elif admin_id:
            all_tags = Tag.objects.filter(admin_id=admin_id)
        else:
            all_tags = Tag.objects.all()
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
