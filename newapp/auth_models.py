"""
Multi-tenant authentication models for SpeedBots.

This module re-exports models from models.py for backward compatibility.
All model definitions are now in models.py to avoid circular imports.
"""

# Re-export models from models.py for backward compatibility
from newapp.models import (
    Organization,
    Role,
    OrganizationUser,
)

__all__ = ['Organization', 'Role', 'OrganizationUser']
