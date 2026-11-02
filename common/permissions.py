from rest_framework import permissions
from apps.memberships.models import TenantMembership, MembershipStatus


class IsPlatformOwner(permissions.BasePermission):
    """
    Allows access only to global platform owners and staff (Avenor Control).
    """
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            (request.user.is_superuser or getattr(request.user, 'is_platform_staff', False))
        )


class IsTenantMember(permissions.BasePermission):
    """
    Allows access only to authenticated users who have an active membership
    within the currently resolved tenant. Attaches request.membership.
    """
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False

        # Platform staff always have oversight access
        if request.user.is_superuser or getattr(request.user, 'is_platform_staff', False):
            return True

        tenant = getattr(request, 'tenant', None)
        if not tenant:
            return False

        membership = TenantMembership.objects.filter(
            tenant=tenant,
            user=request.user,
            status=MembershipStatus.ACTIVE
        ).first()

        if membership:
            request.membership = membership
            return True

        return False


class IsTenantAdmin(permissions.BasePermission):
    """
    Allows access only to tenant administrators (institution_owner or institution_admin)
    or platform staff.
    """
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False

        if request.user.is_superuser or getattr(request.user, 'is_platform_staff', False):
            return True

        tenant = getattr(request, 'tenant', None)
        if not tenant:
            return False

        membership = TenantMembership.objects.filter(
            tenant=tenant,
            user=request.user,
            status=MembershipStatus.ACTIVE
        ).first()

        if membership and membership.is_admin:
            request.membership = membership
            return True

        return False


class HasTenantPermission(permissions.BasePermission):
    """
    Dynamic permission check against granular codenames (e.g. 'courses.create').
    Can be used by setting `required_permission = '...'` on the View,
    or initialized directly via HasTenantPermission.with_perm('...').
    """
    required_permission = None

    def __init__(self, required_permission=None):
        if required_permission:
            self.required_permission = required_permission

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False

        if request.user.is_superuser or getattr(request.user, 'is_platform_staff', False):
            return True

        required_perm = getattr(view, 'required_permission', self.required_permission)
        if not required_perm:
            return True

        tenant = getattr(request, 'tenant', None)
        if not tenant:
            return False

        membership = getattr(request, 'membership', None)
        if not membership:
            membership = TenantMembership.objects.filter(
                tenant=tenant,
                user=request.user,
                status=MembershipStatus.ACTIVE
            ).first()
            if membership:
                request.membership = membership

        if not membership:
            return False

        return membership.has_permission(required_perm)

    @classmethod
    def with_perm(cls, perm_codename):
        """
        Helper factory to use directly in permission_classes:
        permission_classes = [HasTenantPermission.with_perm('courses.create')]
        """
        class _BoundPermission(cls):
            required_permission = perm_codename
        return _BoundPermission
