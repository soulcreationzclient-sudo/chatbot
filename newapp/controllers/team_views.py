"""
Team Management views for Client Admins.

Allows client admins to:
- View team members in their organization
- Add new team members (agents/viewers)
- Edit team member roles
- Deactivate/reactivate team members
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.models import User as DjangoUser
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from django.http import JsonResponse
import json

from newapp.decorators import permission_required
from newapp.models import Organization, Role, OrganizationUser


@permission_required('can_manage_users')
def team_list(request):
    """Team management page — list all members in the current org."""
    org = request.org_user.organization
    if not org:
        messages.error(request, 'No organization associated with your account.')
        return redirect('settings')

    members = OrganizationUser.objects.filter(
        organization=org
    ).select_related('user', 'role').order_by('-role__name', 'user__first_name')

    # Only show roles that client admins can assign (not super_admin)
    assignable_roles = Role.objects.exclude(name=Role.ROLE_SUPER_ADMIN)

    context = {
        'members': members,
        'roles': assignable_roles,
        'organization': org,
    }
    return render(request, 'set/team.html', context)


@permission_required('can_manage_users')
@csrf_protect
@require_http_methods(["POST"])
def team_add(request):
    """Add a new team member to the organization."""
    org = request.org_user.organization
    if not org:
        return JsonResponse({'error': 'No organization found'}, status=400)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    first_name = data.get('first_name', '').strip()
    role_id = data.get('role_id')

    # Validation
    if not username or not password:
        return JsonResponse({'error': 'Username and password are required'}, status=400)

    if len(password) < 6:
        return JsonResponse({'error': 'Password must be at least 6 characters'}, status=400)

    if DjangoUser.objects.filter(username=username).exists():
        return JsonResponse({'error': f'Username "{username}" is already taken'}, status=400)

    if email and DjangoUser.objects.filter(email=email).exists():
        return JsonResponse({'error': f'Email "{email}" is already in use'}, status=400)

    try:
        role = Role.objects.get(id=role_id)
        # Prevent assigning super_admin
        if role.name == Role.ROLE_SUPER_ADMIN:
            return JsonResponse({'error': 'Cannot assign Super Admin role'}, status=403)
    except Role.DoesNotExist:
        return JsonResponse({'error': 'Invalid role selected'}, status=400)

    try:
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

        return JsonResponse({
            'success': True,
            'message': f'Team member "{first_name or username}" added as {role.get_name_display()}'
        })

    except Exception as e:
        return JsonResponse({'error': f'Error creating user: {str(e)}'}, status=500)


@permission_required('can_manage_users')
@csrf_protect
@require_http_methods(["POST"])
def team_update(request, member_id):
    """Update a team member's role or status."""
    org = request.org_user.organization
    if not org:
        return JsonResponse({'error': 'No organization found'}, status=400)

    member = get_object_or_404(OrganizationUser, id=member_id, organization=org)

    # Prevent editing yourself or super admins
    if member.user == request.user:
        return JsonResponse({'error': 'Cannot edit your own role'}, status=403)
    if member.is_super_admin:
        return JsonResponse({'error': 'Cannot edit a Super Admin'}, status=403)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    role_id = data.get('role_id')
    if role_id:
        try:
            role = Role.objects.get(id=role_id)
            if role.name == Role.ROLE_SUPER_ADMIN:
                return JsonResponse({'error': 'Cannot assign Super Admin role'}, status=403)
            member.role = role
        except Role.DoesNotExist:
            return JsonResponse({'error': 'Invalid role'}, status=400)

    # Update name/email if provided
    first_name = data.get('first_name', '').strip()
    email = data.get('email', '').strip()
    if first_name:
        member.user.first_name = first_name
    if email:
        member.user.email = email
    member.user.save()
    member.save()

    return JsonResponse({
        'success': True,
        'message': f'Updated {member.user.first_name or member.user.username}'
    })


@permission_required('can_manage_users')
@csrf_protect
@require_http_methods(["POST"])
def team_toggle(request, member_id):
    """Toggle a team member's active status."""
    org = request.org_user.organization
    if not org:
        return JsonResponse({'error': 'No organization found'}, status=400)

    member = get_object_or_404(OrganizationUser, id=member_id, organization=org)

    if member.user == request.user:
        return JsonResponse({'error': 'Cannot deactivate yourself'}, status=403)
    if member.is_super_admin:
        return JsonResponse({'error': 'Cannot modify a Super Admin'}, status=403)

    member.is_active = not member.is_active
    member.save()

    status = 'activated' if member.is_active else 'deactivated'
    return JsonResponse({
        'success': True,
        'message': f'{member.user.first_name or member.user.username} has been {status}'
    })


@permission_required('can_manage_users')
@csrf_protect
@require_http_methods(["POST"])
def team_delete(request, member_id):
    """Remove a team member from the organization."""
    org = request.org_user.organization
    if not org:
        return JsonResponse({'error': 'No organization found'}, status=400)

    member = get_object_or_404(OrganizationUser, id=member_id, organization=org)

    if member.user == request.user:
        return JsonResponse({'error': 'Cannot remove yourself'}, status=403)
    if member.is_super_admin:
        return JsonResponse({'error': 'Cannot remove a Super Admin'}, status=403)

    username = member.user.username
    django_user = member.user
    member.delete()
    django_user.delete()

    return JsonResponse({
        'success': True,
        'message': f'Removed {username} from the team'
    })
