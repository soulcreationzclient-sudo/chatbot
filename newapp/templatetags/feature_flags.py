"""
Feature Flag template tags for canary deployment.

Usage in templates:
    {% load feature_flags %}

    {# Simple check - show content only for beta orgs #}
    {% if is_beta %}
        <p>New Beta Feature Here!</p>
    {% endif %}

    {# Version-based check #}
    {% if app_version == 'beta' %}
        <p>Beta version content</p>
    {% elif app_version == 'canary' %}
        <p>Canary version content</p>
    {% else %}
        <p>Stable version content</p>
    {% endif %}

Note: is_beta and app_version are auto-injected by the context processor.
      You can also use these template tags for more advanced checks.
"""

from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def get_beta_status(context):
    """
    Returns True if the current organization is a beta tester.
    Usage: {% get_beta_status as is_org_beta %}
    """
    request = context.get('request')
    if not request:
        return False
    
    org = getattr(request, 'current_organization', None)
    if org:
        return getattr(org, 'is_beta_tester', False)
    
    # Fallback: check session for organization_id
    from newapp.models import Organization
    org_id = request.session.get('organization_id')
    if org_id:
        try:
            org = Organization.objects.get(id=org_id)
            return org.is_beta_tester
        except Organization.DoesNotExist:
            pass
    
    return False


@register.simple_tag(takes_context=True)
def get_app_version(context):
    """
    Returns the app_version for the current organization.
    Usage: {% get_app_version as org_version %}
    """
    request = context.get('request')
    if not request:
        return 'stable'
    
    org = getattr(request, 'current_organization', None)
    if org:
        return getattr(org, 'app_version', 'stable')
    
    from newapp.models import Organization
    org_id = request.session.get('organization_id')
    if org_id:
        try:
            org = Organization.objects.get(id=org_id)
            return org.app_version
        except Organization.DoesNotExist:
            pass
    
    return 'stable'


@register.filter
def is_version(org, version):
    """
    Template filter to check if org is a specific version.
    Usage: {% if organization|is_version:"beta" %}...{% endif %}
    """
    if org and hasattr(org, 'app_version'):
        return org.app_version == version
    return version == 'stable'
