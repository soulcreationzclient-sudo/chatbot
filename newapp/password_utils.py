"""
Password utilities with backward compatibility for existing plain-text passwords.

This module provides secure password hashing while maintaining backward compatibility
with existing plain-text passwords in the database.
"""

import hashlib
import bcrypt
from django.contrib.auth.hashers import check_password, make_password


def hash_password(password):
    """
    Hash a password using bcrypt.
    
    Args:
        password: Plain text password
        
    Returns:
        Hashed password (bcrypt format starting with $2b$)
    """
    if not password:
        return None
    
    # Generate salt and hash with bcrypt
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def check_password_hash(stored_password, provided_password):
    """
    Check if provided password matches stored password.
    Supports both bcrypt-hashed and legacy plain-text passwords.
    
    Args:
        stored_password: Password from database (hashed or plain text)
        provided_password: Password to check
        
    Returns:
        True if password matches, False otherwise
    """
    if not stored_password or not provided_password:
        return False
    
    # Check if already hashed with bcrypt
    if stored_password.startswith('$2b$') or stored_password.startswith('$2a$'):
        # Use Django's password checker which handles bcrypt
        return check_password(provided_password, stored_password)
    
    # Legacy: plain-text comparison (for backward compatibility)
    # In production, you should migrate these passwords
    return stored_password == provided_password


def migrate_password(admin_instance):
    """
    Migrate an admin's plain-text password to bcrypt hash.
    
    Args:
        admin_instance: Admin model instance with plain password
        
    Returns:
        True if migration successful, False otherwise
    """
    if not admin_instance.password:
        return False
    
    # Skip if already hashed
    if admin_instance.password.startswith('$2b$') or admin_instance.password.startswith('$2a$'):
        return True
    
    # Hash the plain text password
    hashed = hash_password(admin_instance.password)
    if hashed:
        admin_instance.password = hashed
        admin_instance.save(update_fields=['password'])
        return True
    
    return False


def create_admin_user(email, plain_password, **extra_fields):
    """
    Create a new admin with securely hashed password.
    
    Args:
        email: Admin email
        plain_password: Plain text password (will be hashed)
        **extra_fields: Additional Admin model fields
        
    Returns:
        New Admin instance
    """
    from newapp.models import Admin
    
    hashed_password = hash_password(plain_password)
    
    return Admin.objects.create(
        email=email,
        password=hashed_password,
        **extra_fields
    )


def validate_password_strength(password):
    """
    Validate password meets minimum security requirements.
    
    Args:
        password: Password to validate
        
    Returns:
        (is_valid, error_message) tuple
    """
    if not password:
        return False, "Password is required"
    
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_special = any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in password)
    
    if not (has_upper and has_lower and (has_digit or has_special)):
        return False, "Password must contain uppercase, lowercase, and either digits or special characters"
    
    return True, None
