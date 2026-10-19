from rest_framework import permissions


class IsPlatformAdmin(permissions.BasePermission):
    """
    Allows access only to authenticated, active platform administrators.
    A platform admin is a User with is_staff=True, is_active=True, and no organization.
    Tenant users (even with role OWNER or STAFF) cannot access admin endpoints.
    """
    message = "Platform administrator credentials required."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and user.is_staff
            and getattr(user, 'organization_id', None) is None
        )
