"""
Context processors for feature flags.

These auto-inject variables into every template context, so you can use
{{ is_beta }} and {{ app_version }} in any template without passing them
manually from views.
"""


def feature_flags(request):
    """
    Inject feature flag variables into all template contexts.
    
    Available in templates:
        {{ is_beta }}      - True if current org is a beta tester
        {{ app_version }}  - 'stable', 'beta', or 'canary'
    """
    org = getattr(request, 'current_organization', None)
    
    if org:
        return {
            'is_beta': getattr(org, 'is_beta_tester', False),
            'app_version': getattr(org, 'app_version', 'stable'),
        }
    
    # Fallback: try to get org from session
    from newapp.models import Organization
    org_id = request.session.get('organization_id')
    if org_id:
        try:
            org = Organization.objects.get(id=org_id)
            return {
                'is_beta': org.is_beta_tester,
                'app_version': org.app_version,
            }
        except Organization.DoesNotExist:
            pass
    
    return {
        'is_beta': False,
        'app_version': 'stable',
    }
