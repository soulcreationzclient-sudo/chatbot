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
            # TODO: Add organization_id to Tag model. For now, empty list for new orgs.
            all_tags = []
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
        # return HttpResponse('hi')
        if(request.method=='POST'):
            name=(request.POST.get('name').strip() or '').strip()
            phone_no=(request.POST.get('phone_no')or '').strip()
            if name=='' or phone_no=='':
                messages.warning(request,'name and phone fields cannot be empty')
            if(not User.objects.filter(phone_no=phone_no)):
                admin_id=Admin.objects.get(id=request.session.get('admin_id'))
                User.objects.create(
                    admin_id=admin_id,
                    name=name,
                    phone_no=phone_no,
                    created_at=datetime.now()
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
        user = get_object_or_404(User, id=id)

    # Delete related conversations first to avoid foreign key errors
        user.message_set.all().delete()

    # Delete the user
        user.delete()

    # Redirect to user listing page
        return redirect('show_people')  # replace 'show_people' with your actual user listing url name

    @staticmethod
    def add_user_tag(request):
        from django.http import JsonResponse
        from ..models import Tag, UserTag
        import json

        if request.method != 'POST':
            return JsonResponse({'error': 'Method not allowed'}, status=405)
        
        try:
            data = json.loads(request.body)
            user_id = data.get('user_id')
            tag_id = data.get('tag_id')
            
            if not user_id or not tag_id:
                return JsonResponse({'error': 'Missing user_id or tag_id'}, status=400)
            
            # Verify user and tag belong to admin
            admin_id = request.session.get('admin_id')
            if not admin_id:
                return JsonResponse({'error': 'Not authenticated'}, status=401)
            
            user = User.objects.filter(id=user_id, admin_id=admin_id).first()
            tag = Tag.objects.filter(id=tag_id, admin_id=admin_id).first()
            
            if not user or not tag:
                return JsonResponse({'error': 'User or Tag not found'}, status=404)
            
            # Create if not exists
            UserTag.objects.get_or_create(user=user, tag=tag)
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    @staticmethod
    def remove_user_tag(request):
        from django.http import JsonResponse
        from ..models import Tag, UserTag
        import json

        if request.method != 'POST':
            return JsonResponse({'error': 'Method not allowed'}, status=405)
        
        try:
            data = json.loads(request.body)
            user_id = data.get('user_id')
            tag_id = data.get('tag_id')
            
            if not user_id or not tag_id:
                return JsonResponse({'error': 'Missing user_id or tag_id'}, status=400)
            
            # Verify user and tag belong to admin
            admin_id = request.session.get('admin_id')
            if not admin_id:
                return JsonResponse({'error': 'Not authenticated'}, status=401)
            
            user = User.objects.filter(id=user_id, admin_id=admin_id).first()
            tag = Tag.objects.filter(id=tag_id, admin_id=admin_id).first()
            
            if not user or not tag:
                return JsonResponse({'error': 'User or Tag not found'}, status=404)
            
            # Delete if exists
            UserTag.objects.filter(user=user, tag=tag).delete()
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)