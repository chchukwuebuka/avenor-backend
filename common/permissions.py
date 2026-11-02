from rest_framework import permissions

class IsPlatformOwner(permissions.BasePermission):
    """
    Allows access only to global platform owners (Avenor Control).
    """
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            (request.user.is_superuser or getattr(request.user, 'is_platform_staff', False))
        )
