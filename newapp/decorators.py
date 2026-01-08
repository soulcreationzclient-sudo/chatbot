"""
Permission decorators for role-based access control.

Usage:
    @super_admin_required
    def my_view(request):
        ...
    
    @permission_required('can_manage_users')
    def user_management_view(request):
        ...
"""

from functools import wraps
from django.shortcuts import redirect
from django.http import HttpResponseForbidden
from django.contrib.auth.decorators import login_required


def get_org_user(request):
    """Get the OrganizationUser for the current user."""
    if not request.user.is_authenticated:
        return None
    
    # Try to get from request cache first
    if hasattr(request, '_org_user'):
        return request._org_user
    
    # Import here to avoid circular imports
    from newapp.models import OrganizationUser
    
    try:
        request._org_user = OrganizationUser.objects.select_related(
            'organization', 'role'
        ).get(user=request.user)
        return request._org_user
    except OrganizationUser.DoesNotExist:
        return None


def super_admin_required(view_func):
    """
    Decorator that requires the user to be a Super Admin.
    Redirects to login if not authenticated, returns 403 if not Super Admin.
    """
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        # Debug: Check if user is authenticated
        print(f"[DEBUG] super_admin_required: user.is_authenticated = {request.user.is_authenticated}")
        print(f"[DEBUG] super_admin_required: user = {request.user}")
        
        if not request.user.is_authenticated:
            from django.shortcuts import redirect
            next_url = request.get_full_path()
            return redirect(f'/super-admin/login/?next={next_url}')
        
        org_user = get_org_user(request)
        print(f"[DEBUG] super_admin_required: org_user = {org_user}")
        
        if not org_user:
            print(f"[DEBUG] super_admin_required: No org_user found for user {request.user}")
            return HttpResponseForbidden(
                '<h1>403 Forbidden</h1>'
                '<p>You do not have permission to access this page. (No OrganizationUser)</p>'
                '<p><a href="/">Go to Home</a></p>'
            )
        
        if not org_user.is_super_admin:
            print(f"[DEBUG] super_admin_required: org_user.is_super_admin = {org_user.is_super_admin}")
            return HttpResponseForbidden(
                '<h1>403 Forbidden</h1>'
                '<p>You do not have permission to access this page.</p>'
                '<p><a href="/">Go to Home</a></p>'
            )
        
        # Attach org_user to request for convenience
        request.org_user = org_user
        return view_func(request, *args, **kwargs)
    
    return wrapped


def client_admin_required(view_func):
    """
    Decorator that requires the user to be a Client Admin or higher.
    """
    @wraps(view_func)
    @login_required(login_url='/login/')
    def wrapped(request, *args, **kwargs):
        org_user = get_org_user(request)
        
        if not org_user:
            return HttpResponseForbidden(
                '<h1>403 Forbidden</h1>'
                '<p>You are not associated with any organization.</p>'
            )
        
        if not (org_user.is_super_admin or org_user.is_client_admin):
            return HttpResponseForbidden(
                '<h1>403 Forbidden</h1>'
                '<p>You do not have permission to access this page.</p>'
            )
        
        request.org_user = org_user
        return view_func(request, *args, **kwargs)
    
    return wrapped


def organization_member_required(view_func):
    """
    Decorator that requires the user to be a member of any organization.
    """
    @wraps(view_func)
    @login_required(login_url='/login/')
    def wrapped(request, *args, **kwargs):
        org_user = get_org_user(request)
        
        if not org_user or not org_user.is_active:
            return redirect('login')
        
        request.org_user = org_user
        return view_func(request, *args, **kwargs)
    
    return wrapped


def permission_required(permission_name):
    """
    Decorator factory that requires a specific permission.
    
    Usage:
        @permission_required('can_manage_users')
        def user_management_view(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required(login_url='/login/')
        def wrapped(request, *args, **kwargs):
            org_user = get_org_user(request)
            
            if not org_user:
                return HttpResponseForbidden(
                    '<h1>403 Forbidden</h1>'
                    '<p>You are not associated with any organization.</p>'
                )
            
            if not org_user.has_permission(permission_name):
                return HttpResponseForbidden(
                    f'<h1>403 Forbidden</h1>'
                    f'<p>You do not have the "{permission_name}" permission.</p>'
                )
            
            request.org_user = org_user
            return view_func(request, *args, **kwargs)
        
        return wrapped
    
    return decorator


def organization_context_required(view_func):
    """
    Decorator that ensures the user has an organization context.
    Super Admins must select an organization to work with.
    """
    @wraps(view_func)
    @login_required(login_url='/login/')
    def wrapped(request, *args, **kwargs):
        org_user = get_org_user(request)
        
        if not org_user:
            return redirect('login')
        
        # For Super Admins, check if they have selected an organization
        if org_user.is_super_admin:
            org_id = request.session.get('selected_org_id')
            if org_id:
                from newapp.auth_models import Organization
                try:
                    request.current_organization = Organization.objects.get(id=org_id)
                except Organization.DoesNotExist:
                    request.current_organization = None
            else:
                request.current_organization = None
        else:
            request.current_organization = org_user.organization
        
        request.org_user = org_user
        return view_func(request, *args, **kwargs)
    
    return wrapped
