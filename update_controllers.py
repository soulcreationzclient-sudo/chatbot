
import os
import re

inbox_path = r'c:\Users\Meet\.gemini\chatbot\19 08\chatbot\newapp\controllers\inbox.py'
contact_path = r'c:\Users\Meet\.gemini\chatbot\19 08\chatbot\newapp\controllers\contact.py'
urls_path = r'c:\Users\Meet\.gemini\chatbot\19 08\chatbot\mynewsite\urls.py'

def update_controllers():
    # 1. Update Inboxcontroller: Add filtering and Media Upload logic
    if os.path.exists(inbox_path):
        with open(inbox_path, 'r', encoding='utf-8') as f:
            inbox_content = f.read()
            
        # Add tag filtering to dashboard
        # Look for: selected_user_id = request.GET.get('user_id', '1')
        # Inject tag_id = request.GET.get('tag_id')
        if "tag_id = request.GET.get('tag_id')" not in inbox_content:
            target = "selected_user_id = request.GET.get('user_id', '1')"
            replacement = """selected_user_id = request.GET.get('user_id')
        tag_id = request.GET.get('tag_id')"""
            inbox_content = inbox_content.replace(target, replacement)
            
            # Now filter Logic
            # Look for: users = User.objects.annotate(
            # We need to filter BEFORE or AFTER annotation.
            # Ideally:
            # users = User.objects.all()
            # if tag_id: users = users.filter(usertag__tag_id=tag_id)
            # users = users.annotate(...)
            
            # The current code:
            # users = User.objects.annotate(
            #    last_msg_time=Max('message__created_at')
            # ).order_by('-last_msg_time', 'id')
            
            # Let's verify context with a broader search
            # We will insert the filter logic right after creating `users` query, but wait, `objects.annotate` returns a QuerySet.
            # So I can chain `.filter()` after it.
            
            target_query = ").order_by('-last_msg_time', 'id')"
            if target_query in inbox_content:
                 inbox_content = inbox_content.replace(target_query, target_query + "\n\n        if tag_id:\n            users = users.filter(usertag__tag_id=tag_id)")

        # Add upload_media method
        if "def upload_media(request):" not in inbox_content:
            new_method = """
    from django.core.files.storage import default_storage
    from django.core.files.base import ContentFile
    from django.conf import settings
    from django.http import JsonResponse
    from django.views.decorators.csrf import csrf_exempt

    @csrf_exempt
    def upload_media(request):
        if request.method == 'POST' and request.FILES.get('file'):
            f = request.FILES['file']
            # Save to specific folder
            path = default_storage.save(f'chat_uploads/{f.name}', ContentFile(f.read()))
            url = os.path.join(settings.MEDIA_URL, path).replace('\\\\', '/')
            
            # Determine type
            ftype = 'file'
            if f.content_type.startswith('image'):
                ftype = 'image'
            elif f.content_type.startswith('video'):
                ftype = 'video'
                
            return JsonResponse({'url': url, 'type': ftype})
        return JsonResponse({'error': 'No file provided'}, status=400)
"""
            # Need to import os if not present?
            if "import os" not in inbox_content:
                inbox_content = "import os\n" + inbox_content
                
            inbox_content += new_method

        with open(inbox_path, 'w', encoding='utf-8') as f:
            f.write(inbox_content)
        print("Inboxcontroller updated.")

    # 2. Update Contactcontroller: Add filtering
    if os.path.exists(contact_path):
        with open(contact_path, 'r', encoding='utf-8') as f:
            contact_content = f.read()

        # users = User.objects.filter(admin_id=admin_id)
        if "tag_id = request.GET.get('tag_id')" not in contact_content:
            # We want to insert tag extraction and filtering
            target = "users = User.objects.filter(admin_id=admin_id)"
            replacement = """users = User.objects.filter(admin_id=admin_id)
        
        tag_id = request.GET.get('tag_id')
        if tag_id:
            users = users.filter(usertag__tag_id=tag_id)"""
            
            contact_content = contact_content.replace(target, replacement)
            
        with open(contact_path, 'w', encoding='utf-8') as f:
            f.write(contact_content)
        print("Contactcontroller updated.")

    # 3. Update URLS: Add upload endpoint
    if os.path.exists(urls_path):
        with open(urls_path, 'r', encoding='utf-8') as f:
            urls_content = f.read()
            
        if "api/inbox/upload" not in urls_content:
            # Add to urlpatterns
            # Find the line that adds path('logout/', ...) or similar
            # Or just find 'urlpatterns = [' and append
            # But safer to find a known path and add after
            
            if "path('api/inbox/new_messages', Inboxcontroller.get_new_messages, name='get_new_messages')," in urls_content:
                target = "path('api/inbox/new_messages', Inboxcontroller.get_new_messages, name='get_new_messages'),"
                inject = "\n    path('api/inbox/upload', Inboxcontroller.upload_media, name='inbox_upload_media'),"
                urls_content = urls_content.replace(target, target + inject)
            
        with open(urls_path, 'w', encoding='utf-8') as f:
            f.write(urls_content)
        print("URLs updated.")

if __name__ == "__main__":
    update_controllers()
