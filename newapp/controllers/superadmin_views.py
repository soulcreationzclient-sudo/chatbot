"""
Super Admin views for managing organizations and users.

Provides:
- Dashboard with overview stats
- Organization CRUD
- User management across all organizations
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.models import User as DjangoUser
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from django.utils.text import slugify
from django.db.models import Count

from newapp.models import Organization, Role, OrganizationUser, User as Contact, Message
from newapp.decorators import super_admin_required


@super_admin_required
def super_admin_dashboard(request):
    """Super Admin dashboard with overview statistics."""
    organizations = Organization.objects.prefetch_related('members', 'contacts').order_by('-created_at')[:5]
    
    context = {
        'organizations': organizations,
        'organizations_count': Organization.objects.count(),
        'users_count': OrganizationUser.objects.count(),
        'contacts_count': Contact.objects.count(),
        'messages_count': Message.objects.count(),
    }
    return render(request, 'superadmin/dashboard.html', context)


@super_admin_required
def organization_list(request):
    """List all organizations."""
    organizations = Organization.objects.prefetch_related('members', 'contacts').annotate(
        members_count=Count('members'),
        contacts_count=Count('contacts')
    ).order_by('-created_at')
    
    context = {
        'organizations': organizations,
    }
    return render(request, 'superadmin/organizations.html', context)


@super_admin_required
@csrf_protect
@require_http_methods(["GET", "POST"])
def organization_create(request):
    """Create a new organization with its first Client Admin user."""
    if request.method == 'POST':
        # Organization details
        name = request.POST.get('name', '').strip()
        slug = slugify(name)
        
        # Client Admin details
        admin_username = request.POST.get('admin_username', '').strip()
        admin_email = request.POST.get('admin_email', '').strip()
        admin_password = request.POST.get('admin_password', '')
        admin_first_name = request.POST.get('admin_first_name', '').strip()
        
        # Validation
        errors = []
        if not name:
            errors.append('Organization name is required.')
        if not admin_username:
            errors.append('Client Admin username is required.')
        if not admin_email:
            errors.append('Client Admin email is required.')
        if not admin_password:
            errors.append('Client Admin password is required.')
        elif len(admin_password) < 6:
            errors.append('Password must be at least 6 characters.')
        
        if Organization.objects.filter(slug=slug).exists():
            errors.append(f'An organization with slug "{slug}" already exists.')
        
        if DjangoUser.objects.filter(username=admin_username).exists():
            errors.append(f'Username "{admin_username}" is already taken.')
        
        if DjangoUser.objects.filter(email=admin_email).exists():
            errors.append(f'Email "{admin_email}" is already in use.')
        
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'superadmin/organization_form.html', {
                'name': name,
                'admin_username': admin_username,
                'admin_email': admin_email,
                'admin_first_name': admin_first_name,
            })
        
        try:
            # Create Organization
            org = Organization.objects.create(
                name=name,
                slug=slug,
                is_active=True,
            )
            
            # Get or create Client Admin role
            client_admin_role, _ = Role.objects.get_or_create(
                name=Role.ROLE_CLIENT_ADMIN,
                defaults={
                    'description': 'Full access within organization',
                    'can_manage_users': True,
                    'can_manage_settings': True,
                    'can_manage_tags': True,
                    'can_manage_ai': True,
                    'can_broadcast': True,
                }
            )
            
            # Create Django User
            user = DjangoUser.objects.create_user(
                username=admin_username,
                email=admin_email,
                password=admin_password,
                first_name=admin_first_name,
            )
            
            # Create OrganizationUser
            OrganizationUser.objects.create(
                user=user,
                organization=org,
                role=client_admin_role,
                is_active=True,
            )
            
            # Seed default data for the new organization
            try:
                from ..models import ChatGPTPrompt, Tag
                
                # Default ChatGPT prompt so the bot works immediately
                ChatGPTPrompt.objects.create(
                    organization=org,
                    prompt_text="You are a helpful customer service assistant. Answer questions politely and concisely. If you don't know the answer, let the customer know you'll connect them with a human agent."
                )
                
                # Default tags for common use
                for tag_name in ['New Lead', 'Interested', 'Not Interested']:
                    Tag.objects.create(
                        organization=org,
                        name=tag_name,
                    )
            except Exception as seed_err:
                # Don't fail org creation if seeding fails
                import logging
                logging.getLogger(__name__).warning(f"Default data seeding failed for org {org.id}: {seed_err}")
            
            messages.success(request, f'Organization "{name}" created with admin user "{admin_username}"!')
            return redirect('organization_list')
            
        except Exception as e:
            messages.error(request, f'Error creating organization: {str(e)}')
            return render(request, 'superadmin/organization_form.html')
    
    return render(request, 'superadmin/organization_form.html')


@super_admin_required
def organization_detail(request, pk):
    """View and edit organization details."""
    org = get_object_or_404(Organization, pk=pk)
    members = OrganizationUser.objects.filter(organization=org).select_related('user', 'role')
    contacts = Contact.objects.filter(organization=org).order_by('-created_at')[:10]
    
    context = {
        'organization': org,
        'members': members,
        'contacts': contacts,
        'roles': Role.objects.all(),
    }
    return render(request, 'superadmin/organization_detail.html', context)


@super_admin_required
@csrf_protect
@require_http_methods(["POST"])
def organization_update(request, pk):
    """Update organization details."""
    org = get_object_or_404(Organization, pk=pk)
    
    org.name = request.POST.get('name', org.name)
    org.display_phone_no = request.POST.get('display_phone_no', org.display_phone_no)
    org.whatsapp_phone_id = request.POST.get('whatsapp_phone_id', org.whatsapp_phone_id)
    org.whatsapp_token = request.POST.get('whatsapp_token', org.whatsapp_token)
    org.openai_api_key = request.POST.get('openai_api_key', org.openai_api_key)
    org.is_active = request.POST.get('is_active') == 'on'
    org.save()
    
    messages.success(request, f'Organization "{org.name}" updated successfully!')
    return redirect('organization_detail', pk=org.id)


@super_admin_required
@csrf_protect
@require_http_methods(["POST"])
def organization_toggle_status(request, pk):
    """Toggle organization active status."""
    org = get_object_or_404(Organization, pk=pk)
    org.is_active = not org.is_active
    org.save()
    
    status = 'activated' if org.is_active else 'deactivated'
    messages.success(request, f'Organization "{org.name}" has been {status}.')
    return redirect('organization_list')


@super_admin_required
def super_admin_user_list(request):
    """List all users across all organizations."""
    users = OrganizationUser.objects.select_related(
        'user', 'organization', 'role'
    ).order_by('-created_at')
    
    context = {
        'org_users': users,
        'organizations': Organization.objects.all(),
        'roles': Role.objects.all(),
    }
    return render(request, 'superadmin/users.html', context)


@super_admin_required
@csrf_protect
@require_http_methods(["POST"])
def super_admin_user_create(request):
    """Create a new user for an organization."""
    username = request.POST.get('username', '').strip()
    email = request.POST.get('email', '').strip()
    password = request.POST.get('password', '')
    first_name = request.POST.get('first_name', '').strip()
    last_name = request.POST.get('last_name', '').strip()
    organization_id = request.POST.get('organization_id')
    role_id = request.POST.get('role_id')
    
    if not username or not password:
        messages.error(request, 'Username and password are required.')
        return redirect('super_admin_user_list')
    
    if DjangoUser.objects.filter(username=username).exists():
        messages.error(request, f'Username "{username}" is already taken.')
        return redirect('super_admin_user_list')
    
    try:
        organization = Organization.objects.get(id=organization_id) if organization_id else None
        role = Role.objects.get(id=role_id)
        
        user = DjangoUser.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
        )
        
        OrganizationUser.objects.create(
            user=user,
            organization=organization,
            role=role,
            is_active=True,
        )
        
        messages.success(request, f'User "{username}" created successfully!')
        
    except Exception as e:
        messages.error(request, f'Error creating user: {str(e)}')
    
    return redirect('super_admin_user_list')


@super_admin_required
@csrf_protect
@require_http_methods(["POST"])
def super_admin_user_toggle_status(request, pk):
    """Toggle user active status."""
    org_user = get_object_or_404(OrganizationUser, pk=pk)
    org_user.is_active = not org_user.is_active
    org_user.save()
    
    status = 'activated' if org_user.is_active else 'deactivated'
    messages.success(request, f'User "{org_user.user.username}" has been {status}.')
    return redirect('super_admin_user_list')


@super_admin_required
@csrf_protect
@require_http_methods(["POST"])
def add_user_to_organization(request, org_pk):
    """Add a new user to a specific organization."""
    org = get_object_or_404(Organization, pk=org_pk)
    
    username = request.POST.get('username', '').strip()
    email = request.POST.get('email', '').strip()
    password = request.POST.get('password', '')
    first_name = request.POST.get('first_name', '').strip()
    role_id = request.POST.get('role_id')
    
    if not username or not password:
        messages.error(request, 'Username and password are required.')
        return redirect('organization_detail', pk=org_pk)
    
    if DjangoUser.objects.filter(username=username).exists():
        messages.error(request, f'Username "{username}" is already taken.')
        return redirect('organization_detail', pk=org_pk)
    
    try:
        role = Role.objects.get(id=role_id)
        
        user = DjangoUser.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
        )
        
        OrganizationUser.objects.create(
            user=user,
            organization=org,
            role=role,
            is_active=True,
        )
        
        messages.success(request, f'User "{username}" added to {org.name}!')
        
    except Exception as e:
        messages.error(request, f'Error adding user: {str(e)}')
    
    return redirect('organization_detail', pk=org_pk)


@super_admin_required
@csrf_protect
@require_http_methods(["POST"])
def super_admin_user_update(request, pk):
    """Update user credentials (username, email, name, password)."""
    org_user = get_object_or_404(OrganizationUser, pk=pk)
    user = org_user.user
    
    username = request.POST.get('username', '').strip()
    email = request.POST.get('email', '').strip()
    first_name = request.POST.get('first_name', '').strip()
    last_name = request.POST.get('last_name', '').strip()
    password = request.POST.get('password', '')
    
    # Check if username is being changed and is available
    if username and username != user.username:
        if DjangoUser.objects.filter(username=username).exclude(pk=user.pk).exists():
            messages.error(request, f'Username "{username}" is already taken.')
            return redirect('organization_detail', pk=org_user.organization.id if org_user.organization else None)
        user.username = username
    
    # Update other fields
    if email:
        user.email = email
    if first_name:
        user.first_name = first_name
    if last_name:
        user.last_name = last_name
    
    # Update password if provided
    if password:
        user.set_password(password)
    
    user.save()
    
    messages.success(request, f'User "{user.username}" updated successfully!')
    
    # Redirect back to organization detail if org exists, else to user list
    if org_user.organization:
        return redirect('organization_detail', pk=org_user.organization.id)
    return redirect('super_admin_user_list')
