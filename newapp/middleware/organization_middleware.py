"""
Organization context middleware for multi-tenant system.

This middleware:
1. Attaches the current user's OrganizationUser to the request
2. Attaches the current organization context to the request
3. Provides convenience methods for permission checking
"""

from django.utils.deprecation import MiddlewareMixin


class OrganizationMiddleware(MiddlewareMixin):
    """
    Middleware that attaches organization context to every request.
    
    After this middleware runs, these attributes are available on request:
    - request.org_user: The OrganizationUser instance (or None)
    - request.organization: The current Organization (or None)
    - request.is_super_admin: Boolean
    """
    
    def process_request(self, request):
        # Initialize defaults
        request.org_user = None
        request.organization = None
        request.is_super_admin = False
        
        if not request.user.is_authenticated:
            return None
        
        # Import here to avoid circular imports
        from newapp.models import OrganizationUser, Organization
        
        try:
            org_user = OrganizationUser.objects.select_related(
                'organization', 'role'
            ).get(user=request.user)
            
            request.org_user = org_user
            request.is_super_admin = org_user.is_super_admin
            
            # For super admins, check if they've selected an organization
            if org_user.is_super_admin:
                selected_org_id = request.session.get('selected_org_id')
                if selected_org_id:
                    try:
                        request.organization = Organization.objects.get(id=selected_org_id)
                    except Organization.DoesNotExist:
                        pass
            else:
                request.organization = org_user.organization
                
        except OrganizationUser.DoesNotExist:
            pass
        
        return None
    
    def process_template_response(self, request, response):
        """Add organization context to template context."""
        if hasattr(response, 'context_data') and response.context_data is not None:
            response.context_data['org_user'] = getattr(request, 'org_user', None)
            response.context_data['current_organization'] = getattr(request, 'organization', None)
            response.context_data['is_super_admin'] = getattr(request, 'is_super_admin', False)
        return response
