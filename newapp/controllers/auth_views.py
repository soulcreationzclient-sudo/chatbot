"""
Authentication views for multi-tenant admin system.

Provides:
- Super Admin login/logout
- Client login/logout
- User management helpers
"""

from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User as DjangoUser
from django.contrib import messages
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse

from newapp.models import Organization, Role, OrganizationUser
from newapp.decorators import super_admin_required, organization_member_required


# ============================================================
# Super Admin Views
# ============================================================

@csrf_protect
@require_http_methods(["GET", "POST"])
def super_admin_login(request):
    """Login view for Super Admin portal."""
    # Redirect if already logged in as super admin
    if request.user.is_authenticated:
        try:
            org_user = OrganizationUser.objects.get(user=request.user)
            if org_user.is_super_admin:
                return redirect('super_admin_dashboard')
        except OrganizationUser.DoesNotExist:
            pass
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        
        if not username or not password:
            messages.error(request, 'Please enter both username and password.')
            return render(request, 'superadmin/login.html')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            try:
                org_user = OrganizationUser.objects.get(user=user)
                if org_user.is_super_admin and org_user.is_active:
                    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                    request.session.save()  # Ensure session is saved
                    messages.success(request, f'Welcome, {user.first_name or user.username}!')
                    next_url = request.GET.get('next', 'super_admin_dashboard')
                    return redirect(next_url)
                else:
                    messages.error(request, 'You do not have Super Admin privileges.')
            except OrganizationUser.DoesNotExist:
                messages.error(request, 'User not configured for this portal.')
        else:
            messages.error(request, 'Invalid username or password.')
    
    return render(request, 'superadmin/login.html')


@super_admin_required
def super_admin_logout(request):
    """Logout for Super Admin."""
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('super_admin_login')


# ============================================================
# Client Portal Views
# ============================================================

@csrf_protect
@require_http_methods(["GET", "POST"])
def client_login(request):
    """Login view for Client portal (Client Admin, Agent, Viewer)."""
    # Redirect if already logged in
    if request.user.is_authenticated:
        try:
            org_user = OrganizationUser.objects.get(user=request.user)
            if org_user.is_super_admin:
                return redirect('super_admin_dashboard')
            elif org_user.organization and org_user.is_active:
                return redirect('dashboard')
        except OrganizationUser.DoesNotExist:
            pass
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        
        print(f"[DEBUG] client_login: username='{username}'")
        print(f"[DEBUG] client_login: password repr={repr(password)}")
        
        if not username or not password:
            messages.error(request, 'Please enter both username and password.')
            return render(request, 'login_form.html')
        
        # Check if user exists first
        from django.contrib.auth.models import User as DjangoUser
        try:
            user_obj = DjangoUser.objects.get(username=username)
            print(f"[DEBUG] client_login: user '{username}' exists, is_active={user_obj.is_active}")
            
            # Manual password check since authenticate() is returning None
            if user_obj.check_password(password):
                print(f"[DEBUG] client_login: password check passed!")
                user = user_obj
            else:
                print(f"[DEBUG] client_login: password check FAILED")
                user = None
        except DjangoUser.DoesNotExist:
            print(f"[DEBUG] client_login: user '{username}' does NOT exist")
            user = None
        
        print(f"[DEBUG] client_login: user = {user}")
        
        if user is not None:
            try:
                org_user = OrganizationUser.objects.select_related('organization', 'role').get(user=user)
                
                if not org_user.is_active:
                    messages.error(request, 'Your account has been deactivated.')
                    return render(request, 'login_form.html')
                
                if org_user.is_super_admin:
                    login(request, user)
                    return redirect('super_admin_dashboard')
                
                if org_user.organization and org_user.organization.is_active:
                    login(request, user)
                    # Store organization ID in session for quick access
                    request.session['organization_id'] = org_user.organization.id
                    request.session['organization_name'] = org_user.organization.name
                    request.session.save()  # Ensure session is saved before redirect
                    messages.success(request, f'Welcome, {user.first_name or user.username}!')
                    next_url = request.GET.get('next', 'dashboard')
                    # Use HttpResponseRedirect with no-cache headers to prevent login page caching
                    from django.http import HttpResponseRedirect
                    from django.urls import reverse
                    response = HttpResponseRedirect(reverse(next_url) if not next_url.startswith('/') else next_url)
                    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
                    response['Pragma'] = 'no-cache'
                    response['Expires'] = '0'
                    return response
                else:
                    messages.error(request, 'Your organization is not active.')
                    
            except OrganizationUser.DoesNotExist:
                # Try legacy login with Admin model
                # This allows existing sessions to work during migration
                messages.error(request, 'User not configured correctly. Please contact support.')
        else:
            messages.error(request, 'Invalid username or password.')
    
    return render(request, 'login_form.html')


@organization_member_required
def client_logout(request):
    """Logout for Client portal users."""
    # Clear session data
    request.session.pop('organization_id', None)
    request.session.pop('organization_name', None)
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('login')


# ============================================================
# Helper Functions
# ============================================================

def create_super_admin(username, email, password, first_name='', last_name=''):
    """Helper to create a Super Admin user."""
    # Create or get the super admin role
    role, _ = Role.objects.get_or_create(
        name=Role.ROLE_SUPER_ADMIN,
        defaults={
            'description': 'Full system access',
            'can_manage_organizations': True,
            'can_manage_users': True,
            'can_manage_settings': True,
            'can_manage_tags': True,
            'can_manage_ai': True,
            'can_broadcast': True,
        }
    )
    
    # Create Django user
    user = DjangoUser.objects.create_user(
        username=username,
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
        is_staff=True,
        is_superuser=True,
    )
    
    # Create OrganizationUser (no organization for super admin)
    org_user = OrganizationUser.objects.create(
        user=user,
        organization=None,
        role=role,
        is_active=True,
    )
    
    return user, org_user


def create_client_admin(organization, username, email, password, first_name='', last_name=''):
    """Helper to create a Client Admin user for a specific organization."""
    role, _ = Role.objects.get_or_create(
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
    
    user = DjangoUser.objects.create_user(
        username=username,
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
    )
    
    org_user = OrganizationUser.objects.create(
        user=user,
        organization=organization,
        role=role,
        is_active=True,
    )
    
    return user, org_user


def create_agent(organization, username, email, password, first_name='', last_name=''):
    """Helper to create an Agent user for a specific organization."""
    role, _ = Role.objects.get_or_create(
        name=Role.ROLE_AGENT,
        defaults={
            'description': 'Can view inbox and send messages',
        }
    )
    
    user = DjangoUser.objects.create_user(
        username=username,
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
    )
    
    org_user = OrganizationUser.objects.create(
        user=user,
        organization=organization,
        role=role,
        is_active=True,
    )
    
    return user, org_user
