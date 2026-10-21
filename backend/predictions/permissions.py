"""Permission classes for predictions API endpoints."""

from rest_framework import permissions
from accounts.models import Organization


class IsBusinessOrganizationUser(permissions.BasePermission):
    """Allows access only to authenticated users belonging to a BUSINESS organization.

    NGO users and users without organizations are denied with 403 Forbidden.
    Unauthenticated users receive 401 Unauthorized.
    """
    message = "Predictive inventory planning is only available to commercial business organizations."

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False

        org = getattr(user, "organization", None)
        if not org:
            return False

        return org.org_type == Organization.Type.BUSINESS
