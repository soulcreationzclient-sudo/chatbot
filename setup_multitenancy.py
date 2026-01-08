"""
Setup script to create default roles and initial Super Admin user.

Usage:
    python manage.py shell < setup_multitenancy.py
    
Or run:
    python setup_multitenancy.py

This script:
1. Creates default roles (Super Admin, Client Admin, Agent, Viewer)
2. Creates an initial Super Admin user if none exists
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mynewsite.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

django.setup()

from django.contrib.auth.models import User as DjangoUser
from newapp.models import Role, OrganizationUser


def create_default_roles():
    """Create default roles with appropriate permissions."""
    print("Creating default roles...")
    
    roles_config = [
        {
            'name': Role.ROLE_SUPER_ADMIN,
            'description': 'Full system access. Can manage all organizations and users.',
            'can_manage_organizations': True,
            'can_manage_users': True,
            'can_manage_settings': True,
            'can_view_inbox': True,
            'can_send_messages': True,
            'can_manage_tags': True,
            'can_manage_ai': True,
            'can_manage_contacts': True,
            'can_broadcast': True,
        },
        {
            'name': Role.ROLE_CLIENT_ADMIN,
            'description': 'Full access within their organization.',
            'can_manage_organizations': False,
            'can_manage_users': True,
            'can_manage_settings': True,
            'can_view_inbox': True,
            'can_send_messages': True,
            'can_manage_tags': True,
            'can_manage_ai': True,
            'can_manage_contacts': True,
            'can_broadcast': True,
        },
        {
            'name': Role.ROLE_AGENT,
            'description': 'Can view inbox and send messages.',
            'can_manage_organizations': False,
            'can_manage_users': False,
            'can_manage_settings': False,
            'can_view_inbox': True,
            'can_send_messages': True,
            'can_manage_tags': False,
            'can_manage_ai': False,
            'can_manage_contacts': True,
            'can_broadcast': False,
        },
        {
            'name': Role.ROLE_VIEWER,
            'description': 'Read-only access to inbox and contacts.',
            'can_manage_organizations': False,
            'can_manage_users': False,
            'can_manage_settings': False,
            'can_view_inbox': True,
            'can_send_messages': False,
            'can_manage_tags': False,
            'can_manage_ai': False,
            'can_manage_contacts': False,
            'can_broadcast': False,
        },
    ]
    
    for role_config in roles_config:
        role, created = Role.objects.update_or_create(
            name=role_config['name'],
            defaults=role_config
        )
        status = "Created" if created else "Updated"
        print(f"  {status}: {role.get_name_display()}")
    
    print("✓ Roles setup complete!")
    return Role.objects.all()


def create_super_admin(username='superadmin', email='admin@speedbots.com', password='Admin@123'):
    """Create initial Super Admin user."""
    print("\nChecking for existing Super Admin...")
    
    # Check if super admin already exists
    super_admin_role = Role.objects.filter(name=Role.ROLE_SUPER_ADMIN).first()
    if not super_admin_role:
        print("  Error: Super Admin role not found. Run create_default_roles first.")
        return None
    
    existing_super_admin = OrganizationUser.objects.filter(role=super_admin_role).first()
    if existing_super_admin:
        print(f"  Super Admin already exists: {existing_super_admin.user.username}")
        print("  Skipping creation.")
        return existing_super_admin
    
    # Create Django user
    print(f"\nCreating Super Admin user: {username}")
    
    if DjangoUser.objects.filter(username=username).exists():
        print(f"  Warning: Username '{username}' already exists.")
        user = DjangoUser.objects.get(username=username)
    else:
        user = DjangoUser.objects.create_user(
            username=username,
            email=email,
            password=password,
            is_staff=True,
            is_superuser=True,
        )
        print(f"  Created Django user: {username}")
    
    # Create OrganizationUser
    org_user, created = OrganizationUser.objects.get_or_create(
        user=user,
        defaults={
            'organization': None,  # Super admin has no specific org
            'role': super_admin_role,
            'is_active': True,
        }
    )
    
    if created:
        print(f"  Created OrganizationUser with Super Admin role")
    
    print("\n" + "=" * 50)
    print("✓ SUPER ADMIN SETUP COMPLETE!")
    print("=" * 50)
    print(f"\n  Login URL:  http://127.0.0.1:8000/super-admin/login/")
    print(f"  Username:   {username}")
    print(f"  Password:   {password}")
    print("\n  ⚠️  IMPORTANT: Change the password after first login!")
    print("=" * 50 + "\n")
    
    return org_user


def main():
    print("\n" + "=" * 50)
    print("  SpeedBots Multi-Tenancy Setup")
    print("=" * 50 + "\n")
    
    # Create roles
    create_default_roles()
    
    # Create super admin
    create_super_admin()
    
    print("Setup complete! You can now access the Super Admin portal.\n")


if __name__ == '__main__':
    main()
