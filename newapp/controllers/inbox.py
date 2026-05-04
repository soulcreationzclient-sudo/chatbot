
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
        
        # 24-hour window check variables
        window_expired = False
        hours_since_last_message = None

        if selected_user_id:
            selected_user = User.objects.filter(id=selected_user_id, is_in_inbox=True).first()
            
            # SECURITY: Verify selected user belongs to current org/admin
            if selected_user:
                if org_id and selected_user.organization_id != org_id:
                    selected_user = None  # Don't show cross-tenant data
                elif admin_id:
                    # Handle both admin_id as integer and as Admin object
                    user_admin_id = getattr(selected_user, 'admin_id_id', None)
                    if str(user_admin_id) != str(admin_id):
                        selected_user = None
            
            if selected_user:
                messages = Message.objects.filter(user_id=selected_user_id).order_by('created_at', 'id')
            else:
                messages = []
            
            # Check 24-hour window for selected user
            if selected_user:
                from datetime import timedelta
                last_user_msg = Message.objects.filter(
                    user_id=selected_user, 
                    who='human'  # 'human' = inbound from customer
                ).order_by('-created_at').first()
                
                if last_user_msg:
                    time_since_last_msg = timezone.now() - last_user_msg.created_at
                    hours_since_last_message = int(time_since_last_msg.total_seconds() / 3600)
                    if time_since_last_msg > timedelta(hours=24):
                        window_expired = True
                else:
                    # No inbound messages from user ever - window never opened
                    window_expired = True

        
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
            'window_expired': window_expired,
            'hours_since_last_message': hours_since_last_message,
        })

    def get_new_messages(request):
        user_id = request.GET.get('user_id')
        last_id = request.GET.get('last_id', 0)
        
        if not user_id:
            return JsonResponse({'error': 'Missing user_id'}, status=400)
        
        # SECURITY: Verify user belongs to current org/admin
        org_id = request.session.get('organization_id')
        admin_id = request.session.get('admin_id')
        user = User.objects.filter(id=user_id).first()
        if user:
            if org_id and user.organization_id != org_id:
                return JsonResponse({'error': 'Permission denied'}, status=403)
            if admin_id and str(user.admin_id_id) != str(admin_id):
                return JsonResponse({'error': 'Permission denied'}, status=403)
            
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
            relative_url = os.path.join(settings.MEDIA_URL, path).replace('\\', '/')
            
            # Build full absolute URL so it works when sent via WhatsApp API
            full_url = request.build_absolute_uri(relative_url)
            
            # Determine type
            ftype = 'file'
            if f.content_type.startswith('image'):
                ftype = 'image'
            elif f.content_type.startswith('video'):
                ftype = 'video'
            elif f.content_type.startswith('audio'):
                ftype = 'audio'
            elif f.content_type in ('application/pdf', 'application/msword', 
                                     'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                                     'application/vnd.ms-excel',
                                     'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'):
                ftype = 'document'
                
            return JsonResponse({'url': full_url, 'type': ftype})
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
        
        # SOFT DELETE: Archive from inbox without wiping historical data.
        user.is_in_inbox = False
        user.archived_at = timezone.now()
        user.followup_count = 0
        user.bot_enabled = True
        user.save(update_fields=['is_in_inbox', 'archived_at', 'followup_count', 'bot_enabled'])

        try:
            from ..models import ScheduledFollowUp
            ScheduledFollowUp.objects.filter(user=user, status='pending').update(status='cancelled')
        except Exception:
            pass

        return JsonResponse({'success': True, 'msg': 'Contact archived'})

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
    def get_user_tags(request):
        """Get all tags for a specific user"""
        user_id = request.GET.get('user_id')
        
        if not user_id:
            return JsonResponse({'error': 'Missing user_id'}, status=400)
        
        from ..models import UserTag
        
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
            
            # Get user's tags
            user_tags = UserTag.objects.filter(user=user).select_related('tag')
            tags = [{'id': ut.tag.id, 'name': ut.tag.name} for ut in user_tags]
            
            return JsonResponse({
                'success': True,
                'user_id': user_id,
                'tags': tags
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({'error': str(e)}, status=500)

    @staticmethod
    @csrf_exempt
    def add_user_tag(request):
        """Add an existing or newly named tag to a user from the inbox panel."""
        if request.method != 'POST':
            return JsonResponse({'error': 'POST required'}, status=405)

        import json
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        user_id = data.get('user_id')
        tag_id = data.get('tag_id')
        tag_name = (data.get('tag_name') or '').strip()
        if not user_id or (not tag_id and not tag_name):
            return JsonResponse({'error': 'Missing user_id and tag'}, status=400)

        from ..models import UserTag

        org_id = request.session.get('organization_id')
        admin_id = request.session.get('admin_id')
        if not org_id and not admin_id:
            return JsonResponse({'error': 'Not authenticated'}, status=401)

        if org_id:
            user = User.objects.filter(id=user_id, organization_id=org_id).first()
            tag_qs = Tag.objects.filter(organization_id=org_id)
        else:
            user = User.objects.filter(id=user_id, admin_id=admin_id).first()
            tag_qs = Tag.objects.filter(admin_id=admin_id)

        if not user:
            return JsonResponse({'error': 'User not found'}, status=404)

        tag = tag_qs.filter(id=tag_id).first() if tag_id else None
        if not tag and tag_name:
            tag = tag_qs.filter(name__iexact=tag_name).first()
            if not tag:
                create_kwargs = {'name': tag_name}
                if org_id:
                    create_kwargs['organization_id'] = org_id
                else:
                    create_kwargs['admin_id'] = admin_id
                tag = Tag.objects.create(**create_kwargs)

        if not tag:
            return JsonResponse({'error': 'Tag not found'}, status=404)

        _, created = UserTag.objects.get_or_create(user=user, tag=tag)
        if created:
            try:
                from newapp.controllers.pipeline import run_pipeline_automations
                run_pipeline_automations(user.id, 'tag_applied', tag_id=tag.id)
            except Exception:
                pass

        return JsonResponse({
            'success': True,
            'tag': {'id': tag.id, 'name': tag.name},
            'created': created,
        })

    @staticmethod
    @csrf_exempt
    def remove_user_tag(request):
        """Remove a tag from a user from the inbox panel."""
        if request.method != 'POST':
            return JsonResponse({'error': 'POST required'}, status=405)

        import json
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        user_id = data.get('user_id')
        tag_id = data.get('tag_id')
        tag_name = (data.get('tag_name') or '').strip()
        if not user_id or (not tag_id and not tag_name):
            return JsonResponse({'error': 'Missing user_id and tag'}, status=400)

        from ..models import UserTag

        org_id = request.session.get('organization_id')
        admin_id = request.session.get('admin_id')
        if not org_id and not admin_id:
            return JsonResponse({'error': 'Not authenticated'}, status=401)

        if org_id:
            user = User.objects.filter(id=user_id, organization_id=org_id).first()
            tag_qs = Tag.objects.filter(organization_id=org_id)
        else:
            user = User.objects.filter(id=user_id, admin_id=admin_id).first()
            tag_qs = Tag.objects.filter(admin_id=admin_id)

        if not user:
            return JsonResponse({'error': 'User not found'}, status=404)

        tag = tag_qs.filter(id=tag_id).first() if tag_id else tag_qs.filter(name__iexact=tag_name).first()
        if not tag:
            return JsonResponse({'error': 'Tag not found'}, status=404)

        deleted_count, _ = UserTag.objects.filter(user=user, tag=tag).delete()
        if deleted_count:
            try:
                from newapp.controllers.pipeline import run_pipeline_automations
                run_pipeline_automations(user.id, 'tag_removed', tag_id=tag.id)
            except Exception:
                pass

        return JsonResponse({'success': True, 'removed': bool(deleted_count)})


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

        field_key = field_name.strip().lower()
            
        # Handle standard fields
        if field_key in ['phone_no', 'name']:
            setattr(user, field_key, field_value)
            user.save(update_fields=[field_key])
            return JsonResponse({
                'success': True,
                'message': f"Updated {field_key}: {field_value}",
                'custom_field': {
                    'id': f'std_{field_key}',
                    'name': field_key,
                    'field_type': 'text',
                    'description': f'Standard {field_key.title()}',
                    'value': field_value
                }
            })

        if field_key == 'email':
            from django.core.exceptions import ValidationError
            from django.core.validators import validate_email
            if field_value:
                try:
                    validate_email(field_value)
                except ValidationError:
                    return JsonResponse({'error': 'Invalid email format'}, status=400)

            custom_field = None
            if org_id:
                custom_field = CustomField.objects.filter(
                    organization_id=org_id, name__iexact='email'
                ).first()
                if not custom_field:
                    custom_field = CustomField.objects.create(
                        organization_id=org_id,
                        name='email',
                        field_type='email',
                        description='Standard Email',
                        is_active=True,
                    )
            elif admin_id:
                custom_field = CustomField.objects.filter(
                    admin_id=admin_id, name__iexact='email'
                ).first()
                if not custom_field:
                    custom_field = CustomField.objects.create(
                        admin_id=admin_id,
                        name='email',
                        field_type='email',
                        description='Standard Email',
                        is_active=True,
                    )

            if not custom_field:
                return JsonResponse({'error': "Custom field 'email' not found"}, status=404)

            cf_value, _ = CustomFieldValue.objects.update_or_create(
                custom_field=custom_field,
                user=user,
                defaults={'value': field_value}
            )

            try:
                from newapp.controllers.pipeline import run_pipeline_automations
                run_pipeline_automations(
                    user.id, 'custom_field_changed',
                    field_name='email', field_value=str(field_value)
                )
            except Exception:
                pass

            return JsonResponse({
                'success': True,
                'message': f"Updated email: {field_value}",
                'custom_field': {
                    'id': 'std_email',
                    'name': 'email',
                    'field_type': 'email',
                    'description': 'Standard Email',
                    'value': cf_value.value or ''
                }
            })
        
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
            
            # Trigger pipeline automations on field change
            try:
                from newapp.controllers.pipeline import run_pipeline_automations
                run_pipeline_automations(
                    user.id, 'custom_field_changed',
                    field_name=field_name, field_value=str(field_value)
                )
            except Exception:
                pass  # Don't break custom field flow
            
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

        field_key = field_name.strip().lower()
            
        # Handle standard fields
        if field_key in ['phone_no', 'name']:
            setattr(user, field_key, '')
            user.save(update_fields=[field_key])
            return JsonResponse({
                'success': True,
                'message': f"Cleared {field_key}"
            })

        if field_key == 'email':
            custom_field = None
            if org_id:
                custom_field = CustomField.objects.filter(
                    organization_id=org_id, name__iexact='email'
                ).first()
            elif admin_id:
                custom_field = CustomField.objects.filter(
                    admin_id=admin_id, name__iexact='email'
                ).first()
            if custom_field:
                CustomFieldValue.objects.filter(custom_field=custom_field, user=user).delete()
                try:
                    from newapp.controllers.pipeline import run_pipeline_automations
                    run_pipeline_automations(
                        user.id, 'custom_field_changed',
                        field_name='email', field_value=''
                    )
                except Exception:
                    pass
            return JsonResponse({
                'success': True,
                'message': 'Cleared email'
            })
        
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

    @staticmethod
    @csrf_exempt
    def get_user_logs(request):
        """Get recent logs for a specific user (for inbox right panel)"""
        user_id = request.GET.get('user_id')
        days = request.GET.get('days', '1')  # Default: last 24 hours
        log_type = request.GET.get('log_type')  # Optional filter by log type
        limit = request.GET.get('limit', '50')  # Default limit: 50 logs

        if not user_id:
            return JsonResponse({'error': 'Missing user_id'}, status=400)

        from ..models import UserLog
        from datetime import datetime, timedelta

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

            # Build query with filters
            from django.utils import timezone
            now = timezone.now()
            days_ago = now - timedelta(days=int(days))

            logs_query = UserLog.objects.filter(
                user=user,
                created_at__gte=days_ago
            )

            # Optional log_type filter
            if log_type:
                logs_query = logs_query.filter(log_type=log_type)

            # Order by newest first and apply limit
            logs = logs_query.order_by('-created_at')[:int(limit)]

            # Format logs for response
            logs_data = []
            for log in logs:
                logs_data.append({
                    'id': log.id,
                    'log_type': log.log_type,
                    'level': log.level,
                    'message': log.message,
                    'metadata': log.metadata or {},
                    'created_at': log.created_at.isoformat()
                })

            return JsonResponse({
                'success': True,
                'user_id': user_id,
                'count': len(logs_data),
                'logs': logs_data
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({'error': str(e)}, status=500)

    @staticmethod
    @csrf_exempt
    def create_user_log(request):
        """Create a new log entry for a user (used by other parts of the app)"""
        if request.method != 'POST':
            return JsonResponse({'error': 'POST required'}, status=405)

        import json
        try:
            data = json.loads(request.body)
            user_id = data.get('user_id')
            log_type = data.get('log_type', 'system')
            level = data.get('level', 'info')
            message = data.get('message')
            metadata = data.get('metadata', {})
        except:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        if not user_id or not message:
            return JsonResponse({'error': 'Missing user_id or message'}, status=400)

        from ..models import UserLog

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

        try:
            log = UserLog.objects.create(
                user=user,
                admin_id=admin_id,
                organization_id=org_id,
                log_type=log_type,
                level=level,
                message=message,
                metadata=metadata
            )

            return JsonResponse({
                'success': True,
                'log_id': log.id,
                'message': 'Log created successfully'
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    @staticmethod
    def export_chat_csv(request, user_id):
        """Export a contact's chat history as CSV file."""
        import csv

        org_id = request.session.get('organization_id')
        admin_id = request.session.get('admin_id')

        if not org_id and not admin_id:
            return HttpResponse('Not authenticated', status=401)

        user = User.objects.filter(id=user_id).first()
        if not user:
            return HttpResponse('User not found', status=404)

        # Security check
        if org_id and user.organization_id != org_id:
            return HttpResponse('Permission denied', status=403)
        if admin_id and str(user.admin_id_id) != str(admin_id):
            return HttpResponse('Permission denied', status=403)

        msgs = Message.objects.filter(user_id=user).order_by('created_at', 'id')

        contact_name = user.name or user.phone_no or f'user_{user_id}'
        safe_name = "".join(c for c in contact_name if c.isalnum() or c in (' ', '-', '_')).strip()

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="chat_{safe_name}.csv"'
        response.write('\ufeff')  # UTF-8 BOM for Excel

        writer = csv.writer(response)
        writer.writerow(['Date', 'Time', 'From', 'Message'])

        for m in msgs:
            created = m.created_at
            sender = 'Bot/Agent' if m.who == 'bot' else 'Customer'
            writer.writerow([
                created.strftime('%Y-%m-%d'),
                created.strftime('%H:%M:%S'),
                sender,
                m.messages or ''
            ])

        return response
