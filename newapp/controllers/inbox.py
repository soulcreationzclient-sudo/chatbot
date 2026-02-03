
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
from django.utils import timezone

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
            # Also filter by is_in_inbox=True for inbox view (soft-delete support)
            users = User.objects.filter(
                organization_id=org_id,
                is_in_inbox=True  # Only show non-archived contacts in inbox
            ).annotate(
                last_msg_time=Max('message__created_at')
            ).order_by('-last_msg_time', 'id')
        elif admin_id:
            users = User.objects.filter(
                admin_id=admin_id,
                is_in_inbox=True  # Only show non-archived contacts in inbox
            ).annotate(
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
        """Archive a user from inbox (soft-delete - preserves data)"""
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
        
        # SOFT DELETE: Archive from inbox instead of deleting
        # Contact remains in All Contacts view and all data is preserved
        user.is_in_inbox = False
        user.archived_at = timezone.now()
        user.save(update_fields=['is_in_inbox', 'archived_at'])
        
        # CUSTOM DELETE LOGIC:
        # User requested: Remove tags and delete history, but keep contact.
        from ..models import UserTag, Message
        # 1. Remove all tags
        UserTag.objects.filter(user=user).delete()
        # 2. Delete message history
        Message.objects.filter(user=user).delete()
        
        return JsonResponse({'success': True, 'msg': 'Contact archived from inbox'})

    @csrf_exempt
    def restore_user(request, user_id):
        """Restore an archived user back to the inbox"""
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
        
        # Restore to inbox
        user.is_in_inbox = True
        user.archived_at = None
        user.save(update_fields=['is_in_inbox', 'archived_at'])
        
        return JsonResponse({'success': True, 'msg': 'Contact restored to inbox'})

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


    @staticmethod
    @csrf_exempt
    def get_user_custom_fields(request):
        """Get all custom field values for a specific user"""
        user_id = request.GET.get('user_id')
        
        if not user_id:
            return JsonResponse({'error': 'Missing user_id'}, status=400)
        
        from ..models import CustomFieldValue, Admin, Organization
        from newapp.custom_field_processor import format_custom_fields_for_inbox
        
        try:
            # Get user and verify ownership
            user = User.objects.filter(id=user_id).first()
            if not user:
                return JsonResponse({'error': 'User not found'}, status=404)
            
            org_id = request.session.get('organization_id')
            admin_id = request.session.get('admin_id')
            
            # Security check
            if org_id and user.organization_id != org_id:
                return JsonResponse({'error': 'Permission denied'}, status=403)
            if admin_id and str(user.admin_id_id) != str(admin_id):
                return JsonResponse({'error': 'Permission denied'}, status=403)
            
            # Get admin/org objects for the processor
            admin = None
            org = None
            if org_id:
                org = Organization.objects.filter(id=org_id).first()
            if admin_id:
                admin = Admin.objects.filter(id=admin_id).first()
            
            # Get custom field values formatted for inbox
            fields = format_custom_fields_for_inbox(user, admin, org)
            
            return JsonResponse({
                'success': True,
                'user_id': user_id,
                'custom_fields': fields
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({'error': str(e)}, status=500)

    @staticmethod
    @csrf_exempt
    def update_user_custom_field(request):
        """Update a custom field value for a user"""
        if request.method != 'POST':
            return JsonResponse({'error': 'POST required'}, status=405)
        
        import json
        try:
            data = json.loads(request.body)
            user_id = data.get('user_id')
            field_name = data.get('field_name')
            field_value = data.get('value')
        except:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        
        if not user_id or not field_name:
            return JsonResponse({'error': 'Missing user_id or field_name'}, status=400)
        
        from ..models import CustomField, CustomFieldValue
        
        org_id = request.session.get('organization_id')
        admin_id = request.session.get('admin_id')
        
        if not org_id and not admin_id:
            return JsonResponse({'error': 'Not authenticated'}, status=401)
        
        # Get user and verify ownership
        user = User.objects.filter(id=user_id).first()
        if not user:
            return JsonResponse({'error': 'User not found'}, status=404)
        
        # Security check
        if org_id and user.organization_id != org_id:
            return JsonResponse({'error': 'Permission denied'}, status=403)
        if admin_id and str(user.admin_id_id) != str(admin_id):
            return JsonResponse({'error': 'Permission denied'}, status=403)
        
        # Find the custom field
        custom_field = None
        if org_id:
            custom_field = CustomField.objects.filter(
                organization_id=org_id,
                name=field_name,
                is_active=True
            ).first()
        if not custom_field and admin_id:
            custom_field = CustomField.objects.filter(
                admin_id=admin_id,
                name=field_name,
                is_active=True
            ).first()
        
        if not custom_field:
            return JsonResponse({'error': f"Custom field '{field_name}' not found"}, status=404)
        
        # Update or create the field value
        try:
            field_value_obj, created = CustomFieldValue.objects.update_or_create(
                custom_field=custom_field,
                user=user,
                defaults={
                    'value': field_value,
                    'updated_at': timezone.now()
                }
            )
            
            action = "Created" if created else "Updated"
            return JsonResponse({
                'success': True,
                'message': f"{action} {field_name}: {field_value}",
                'custom_field': {
                    'id': custom_field.id,
                    'name': custom_field.name,
                    'field_type': custom_field.field_type,
                    'description': custom_field.description or '',
                    'value': field_value
                }
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    @staticmethod
    @csrf_exempt
    def delete_user_custom_field(request):
        """Delete a custom field value for a user"""
        if request.method != 'POST':
            return JsonResponse({'error': 'POST required'}, status=405)
        
        import json
        try:
            data = json.loads(request.body)
            user_id = data.get('user_id')
            field_name = data.get('field_name')
        except:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        
        if not user_id or not field_name:
            return JsonResponse({'error': 'Missing user_id or field_name'}, status=400)
        
        from ..models import CustomField, CustomFieldValue
        
        org_id = request.session.get('organization_id')
        admin_id = request.session.get('admin_id')
        
        if not org_id and not admin_id:
            return JsonResponse({'error': 'Not authenticated'}, status=401)
        
        # Get user and verify ownership
        user = User.objects.filter(id=user_id).first()
        if not user:
            return JsonResponse({'error': 'User not found'}, status=404)
        
        # Security check
        if org_id and user.organization_id != org_id:
            return JsonResponse({'error': 'Permission denied'}, status=403)
        if admin_id and str(user.admin_id_id) != str(admin_id):
            return JsonResponse({'error': 'Permission denied'}, status=403)
        
        # Find the custom field
        custom_field = None
        if org_id:
            custom_field = CustomField.objects.filter(
                organization_id=org_id,
                name=field_name,
                is_active=True
            ).first()
        if not custom_field and admin_id:
            custom_field = CustomField.objects.filter(
                admin_id=admin_id,
                name=field_name,
                is_active=True
            ).first()
        
        if not custom_field:
            return JsonResponse({'error': f"Custom field '{field_name}' not found"}, status=404)
        
        # Delete the field value
        try:
            deleted, _ = CustomFieldValue.objects.filter(
                custom_field=custom_field,
                user=user
            ).delete()
            
            if deleted:
                return JsonResponse({
                    'success': True,
                    'message': f"Deleted {field_name}"
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': f"No value found for {field_name}"
                })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
