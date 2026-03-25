from django.db.models import Max, Q
from datetime import timedelta
from django.utils import timezone
import datetime
from ..models import CustomField, CustomFieldValue
from django.http import HttpResponse
from django.shortcuts import render,redirect
from ..models import User
from ..models import Message
from django.contrib import messages
from newapp.models import Admin
from datetime import datetime
from django.shortcuts import get_object_or_404
from newapp.forms import UserForm
from django.views.decorators.csrf import csrf_exempt
from newapp.models import User, UserTag






import re

def validate_phone_number(phone_no):
    """Validate phone number format - allows digits, spaces, +, -, parentheses"""
    if not phone_no:
        return False, "Phone number is required"
    # Remove common formatting characters
    cleaned = re.sub(r"[\s\-\(\)]", "", phone_no)
    # Check if only digits remain
    if not cleaned.isdigit():
        return False, "Phone number can only contain digits and common formatting characters"
    # Check minimum length (typical phone numbers are at least 7-10 digits)
    if len(cleaned) < 7:
        return False, "Phone number is too short"
    if len(cleaned) > 15:
        return False, "Phone number is too long"
    return True, None

def validate_name(name):
    """Validate name field - check length and basic characters"""
    if not name:
        return False, "Name is required"
    # Check minimum length
    if len(name.strip()) < 2:
        return False, "Name must be at least 2 characters long"
    # Check maximum length
    if len(name.strip()) > 100:
        return False, "Name must be less than 100 characters"
    # Allow letters, numbers, spaces, and common special characters
    if not re.match(r"^[\w\s\.\-\'\"\.]+$", name):
        return False, "Name contains invalid characters"
    return True, None

class Contactcontroller:

    def dashboard(request):
    # Support both new organization-based auth and legacy admin auth
        org_id = request.session.get("organization_id")
        admin_id = request.session.get("admin_id")

        if org_id:
            # filter users by organization
            users = User.objects.filter(organization_id=org_id).annotate(
                last_seen=Max('message__created_at')
            ).order_by('-created_at')
        elif admin_id:
            # filter users by admin_id (legacy)
            users = User.objects.filter(admin_id=admin_id).annotate(
                last_seen=Max('message__created_at')
            ).order_by('-created_at')
        else:
            return redirect("/login")   # or return an error if not logged in

        # --- Filter Logic ---
        tag_id = request.GET.get('tag_id')
        if tag_id:
            users = users.filter(usertag__tag_id=tag_id)

        source = request.GET.get('source')
        if source and source.lower() != 'all':
             users = users.filter(source__iexact=source)

        timeframe = request.GET.get('timeframe')
        if timeframe:
            now = timezone.now()
            if timeframe == '24h':
                users = users.filter(last_seen__gte=now - timedelta(hours=24))
            elif timeframe == '7d':
                users = users.filter(last_seen__gte=now - timedelta(days=7))
            elif timeframe == '30d':
                users = users.filter(last_seen__gte=now - timedelta(days=30))
            elif timeframe == 'custom':
                s_date = request.GET.get('start_date')
                e_date = request.GET.get('end_date')
                if s_date:
                    users = users.filter(last_seen__gte=s_date)
                if e_date:
                    # Make end date inclusive of the day
                    # This simplest way is typically strictly string compare or casting.
                    # Django handles string dates well usually.
                    users = users.filter(last_seen__lte=e_date + ' 23:59:59')
        
        tag_id = request.GET.get('tag_id')
        if tag_id:
            users = users.filter(usertag__tag_id=tag_id)

        # Add tags list to each user instance
        from ..models import Tag
        
        if org_id:
            # Filter tags by organization
            all_tags = Tag.objects.filter(organization_id=org_id)
        else:
            all_tags = Tag.objects.filter(admin_id=admin_id)
        
        for user in users:
            user_tags = UserTag.objects.filter(user=user).select_related('tag')
            user.tags = [ut.tag.name for ut in user_tags]
            user.tag_ids = [ut.tag.id for ut in user_tags]

        return render(request, "contact/dashboard.html", {"users": users, "all_tags": all_tags})
    
    def add_user(request):
        return render(request,'contact/add_user.html')
    
    @csrf_exempt
    def add_admin_user(request):
        if(request.method=='POST'):
            name=(request.POST.get('name').strip() or '').strip()
            phone_no=(request.POST.get('phone_no')or '').strip()
            # Use validation functions
            is_valid, error = validate_name(name)
            if not is_valid:
                messages.warning(request, error)
                return redirect(request.META.get("HTTP_REFERER", "contact/add"))
            
            is_valid, error = validate_phone_number(phone_no)
            if not is_valid:
                messages.warning(request, error)
                return redirect(request.META.get("HTTP_REFERER", "contact/add"))
            
            # Support both organization and admin auth
            org_id = request.session.get('organization_id')
            admin_id = request.session.get('admin_id')

            # Check duplicate within the SAME org/admin only (not globally)
            if org_id:
                phone_exists = User.objects.filter(phone_no=phone_no, organization_id=org_id).exists()
            elif admin_id:
                phone_exists = User.objects.filter(phone_no=phone_no, admin_id=admin_id).exists()
            else:
                messages.error(request, 'Not authenticated')
                return redirect('/login')

            if not phone_exists:
                if org_id:
                    from ..models import Organization
                    org = Organization.objects.filter(id=org_id).first()
                    User.objects.create(
                        organization=org,
                        name=name,
                        phone_no=phone_no,
                        created_at=timezone.now(),
                        is_in_inbox=True
                    )
                else:
                    admin = Admin.objects.filter(id=admin_id).first()
                    if not admin:
                        messages.error(request, 'Admin not found')
                        return redirect(request.META.get("HTTP_REFERER", "contact/add"))
                    User.objects.create(
                        admin_id=admin,
                        name=name,
                        phone_no=phone_no,
                        created_at=timezone.now(),
                        is_in_inbox=True
                    )
                    
                messages.success(request,'successfully inserted')
                return redirect(request.META.get("HTTP_REFERER", "contact/add"))
            else:
                 messages.warning(request,'already mobile number exists')
                 return redirect(request.META.get("HTTP_REFERER", "contact/add"))
        else:
            return HttpResponse('not correct method')

    
    def edit_user(request, id):
        user = get_object_or_404(User, id=id)
        if request.method == 'POST':
            form = UserForm(request.POST, instance=user)
            if form.is_valid():
                form.save()
                # Save Custom Fields
                for key, value in request.POST.items():
                    if key.startswith('custom_field_'):
                        try:
                            cf_id = int(key.split('_')[2])
                            cf = CustomField.objects.get(id=cf_id)
                            CustomFieldValue.objects.update_or_create(
                                custom_field=cf, user=user,
                                defaults={'value': value}
                            )
                        except:
                            pass

                return redirect('show_people')  # Adjust to your user list view
        else:
            form = UserForm(instance=user)
        custom_fields = CustomField.objects.filter(admin_id=request.session.get('admin_id'))
        for cf in custom_fields:
            val = CustomFieldValue.objects.filter(custom_field=cf, user=user).first()
            cf.value = val.value if val else ''

        return render(request, 'contact/edit_user.html', {'form': form, 'user': user, 'custom_fields': custom_fields})

    def delete_user(request, id):
        """Delete a user and all associated data"""
        user = get_object_or_404(User, id=id)

        # Delete associated data first
        UserTag.objects.filter(user=user).delete()
        Message.objects.filter(user_id=user).delete()
        
        # Hard delete the user record
        user.delete()

        # Redirect to My Contacts page
        return redirect('contact_dashboard')

    @staticmethod
    def add_user_tag(request):
        from django.http import JsonResponse
        from ..models import Tag, UserTag, Organization
        import json

        if request.method != 'POST':
            return JsonResponse({'error': 'Method not allowed'}, status=405)
        
        try:
            data = json.loads(request.body)
            user_id = data.get('user_id')
            tag_id = data.get('tag_id')
            
            if not user_id or not tag_id:
                return JsonResponse({'error': 'Missing user_id or tag_id'}, status=400)
            
            # Support both organization and admin auth
            org_id = request.session.get('organization_id')
            admin_id = request.session.get('admin_id')
            
            if org_id:
                user = User.objects.filter(id=user_id, organization_id=org_id).first()
                tag = Tag.objects.filter(id=tag_id, organization_id=org_id).first()
            elif admin_id:
                user = User.objects.filter(id=user_id, admin_id=admin_id).first()
                tag = Tag.objects.filter(id=tag_id, admin_id=admin_id).first()
            else:
                return JsonResponse({'error': 'Not authenticated'}, status=401)
            
            if not user or not tag:
                return JsonResponse({'error': 'User or Tag not found'}, status=404)
            
            # Create if not exists
            obj, created = UserTag.objects.get_or_create(user=user, tag=tag)
            
            # Trigger pipeline automations if tag was newly applied
            if created:
                try:
                    from newapp.controllers.pipeline import run_pipeline_automations
                    run_pipeline_automations(user.id, 'tag_applied', tag_id=tag.id)
                except Exception:
                    pass  # Don't break tag flow if automation fails
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    @staticmethod
    def remove_user_tag(request):
        from django.http import JsonResponse
        from ..models import Tag, UserTag, Organization
        import json

        if request.method != 'POST':
            return JsonResponse({'error': 'Method not allowed'}, status=405)
        
        try:
            data = json.loads(request.body)
            user_id = data.get('user_id')
            tag_id = data.get('tag_id')
            
            if not user_id or not tag_id:
                return JsonResponse({'error': 'Missing user_id or tag_id'}, status=400)
            
            # Support both organization and admin auth
            org_id = request.session.get('organization_id')
            admin_id = request.session.get('admin_id')
            
            if org_id:
                user = User.objects.filter(id=user_id, organization_id=org_id).first()
                tag = Tag.objects.filter(id=tag_id, organization_id=org_id).first()
            elif admin_id:
                user = User.objects.filter(id=user_id, admin_id=admin_id).first()
                tag = Tag.objects.filter(id=tag_id, admin_id=admin_id).first()
            else:
                return JsonResponse({'error': 'Not authenticated'}, status=401)
            
            if not user:
                return JsonResponse({'error': 'User not found'}, status=404)
            
            # If tag exists, delete normally. If tag was deleted, clean up orphan UserTag
            if tag:
                UserTag.objects.filter(user=user, tag=tag).delete()
            else:
                # Tag was deleted - clean up orphan UserTag by tag_id directly
                deleted_count, _ = UserTag.objects.filter(user=user, tag_id=tag_id).delete()
                if deleted_count == 0:
                    # Also try to clean up any orphan tags for this user
                    UserTag.objects.filter(user=user, tag__isnull=True).delete()
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    @staticmethod
    def contact_search_api(request):
        """
        Advanced server-side contact search API.
        
        Query Parameters:
        - q: Search query (searches name and phone number)
        - tag_id: Filter by tag ID
        - source: Filter by source (e.g., 'Whatsapp')
        - timeframe: Filter by timeframe ('24h', '7d', '30d', 'custom')
        - start_date: Start date for custom timeframe filter
        - end_date: End date for custom timeframe filter
        - page: Page number (default: 1)
        - page_size: Results per page (default: 20, max: 100)
        - sort_by: Sort field (name, phone_no, created_at, last_seen)
        - sort_order: Sort order (asc, desc)
        """
        from django.http import JsonResponse
        from ..models import Tag
        
        # Authentication check
        org_id = request.session.get("organization_id")
        admin_id = request.session.get("admin_id")
        
        if not org_id and not admin_id:
            return JsonResponse({"error": "Not authenticated"}, status=401)
        
        try:
            # Get query parameters
            query = request.GET.get("q", "").strip()
            tag_id = request.GET.get("tag_id")
            source = request.GET.get("source")
            timeframe = request.GET.get("timeframe")
            start_date = request.GET.get("start_date")
            end_date = request.GET.get("end_date")
            
            # Pagination
            try:
                page = int(request.GET.get("page", 1))
                page_size = min(int(request.GET.get("page_size", 20)), 100)
            except ValueError:
                page = 1
                page_size = 20
            
            # Sorting
            sort_by = request.GET.get("sort_by", "created_at")
            sort_order = request.GET.get("sort_order", "desc")
            
            # Validate sort fields
            valid_sort_fields = ["name", "phone_no", "created_at", "last_seen"]
            if sort_by not in valid_sort_fields:
                sort_by = "created_at"
            
            # Build the base queryset
            if org_id:
                queryset = User.objects.filter(organization_id=org_id)
            else:
                queryset = User.objects.filter(admin_id=admin_id)
            
            # Add last_seen annotation
            queryset = queryset.annotate(
                last_seen=Max("message__created_at")
            )
            
            # Apply search query
            if query:
                queryset = queryset.filter(
                    Q(name__icontains=query) |
                    Q(phone_no__icontains=query)
                )
            
            # Apply tag filter
            if tag_id:
                queryset = queryset.filter(usertag__tag_id=tag_id)
            
            # Apply source filter
            if source and source.lower() != "all":
                queryset = queryset.filter(source__iexact=source)
            
            # Apply timeframe filter
            if timeframe:
                now = timezone.now()
                if timeframe == "24h":
                    queryset = queryset.filter(last_seen__gte=now - timedelta(hours=24))
                elif timeframe == "7d":
                    queryset = queryset.filter(last_seen__gte=now - timedelta(days=7))
                elif timeframe == "30d":
                    queryset = queryset.filter(last_seen__gte=now - timedelta(days=30))
                elif timeframe == "custom" and start_date:
                    queryset = queryset.filter(last_seen__gte=start_date)
                    if end_date:
                        queryset = queryset.filter(last_seen__lte=end_date + " 23:59:59")
            
            # Apply sorting
            sort_prefix = "-" if sort_order.lower() == "desc" else ""
            queryset = queryset.order_by(f"{sort_prefix}{sort_by}")
            
            # Get total count
            total_count = queryset.count()
            
            # Apply pagination
            offset = (page - 1) * page_size
            users = queryset[offset:offset + page_size]
            
            # Build response
            results = []
            for user in users:
                user_tags = UserTag.objects.filter(user=user).select_related("tag")
                tags = [{"id": ut.tag.id, "name": ut.tag.name} for ut in user_tags]
                
                results.append({
                    "id": user.id,
                    "name": user.name,
                    "phone_no": user.phone_no,
                    "source": user.source,
                    "created_at": user.created_at.isoformat() if user.created_at else None,
                    "last_seen": user.last_seen.isoformat() if user.last_seen else None,
                    "is_in_inbox": user.is_in_inbox,
                    "bot_enabled": user.bot_enabled,
                    "tags": tags,
                    "followup_count": user.followup_count,
                })
            
            return JsonResponse({
                "success": True,
                "data": results,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total_count": total_count,
                    "total_pages": (total_count + page_size - 1) // page_size,
                    "has_next": offset + page_size < total_count,
                    "has_prev": page > 1,
                }
            })
            
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)