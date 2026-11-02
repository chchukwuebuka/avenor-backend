import secrets
import uuid
from datetime import timedelta
from django.conf import settings
from django.db import models
from django.utils import timezone
from apps.tenants.models import Tenant, TenantManager


class Permission(models.Model):
    """
    Granular system permission (e.g., courses.create, members.invite).
    """
    codename = models.CharField(max_length=100, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    module = models.CharField(max_length=100, db_index=True)
    description = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Permission'
        verbose_name_plural = 'Permissions'
        ordering = ['module', 'codename']

    def __str__(self):
        return f"{self.module}:{self.codename}"


class Role(models.Model):
    """
    Role defining a set of permissions. Can be institutional (e.g. instructor)
    or platform-wide (e.g. platform_owner).
    """
    slug = models.SlugField(max_length=100, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    is_platform_role = models.BooleanField(default=False, db_index=True)
    permissions = models.ManyToManyField(
        Permission,
        through='RolePermission',
        related_name='roles',
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Role'
        verbose_name_plural = 'Roles'
        ordering = ['slug']

    def __str__(self):
        prefix = "[Platform]" if self.is_platform_role else "[Tenant]"
        return f"{prefix} {self.name} ({self.slug})"


class RolePermission(models.Model):
    """
    Through table linking Roles to granular Permissions.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='role_permissions')
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, related_name='permission_roles')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Role Permission'
        verbose_name_plural = 'Role Permissions'
        unique_together = ('role', 'permission')

    def __str__(self):
        return f"{self.role.slug} -> {self.permission.codename}"


class MembershipStatus(models.TextChoices):
    INVITED = 'invited', 'Invited'
    ACTIVE = 'active', 'Active'
    SUSPENDED = 'suspended', 'Suspended'
    REMOVED = 'removed', 'Removed'


class TenantMembership(models.Model):
    """
    Links a User to a specific Tenant with designated status and roles.
    Enforces strict multi-tenant boundaries.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='memberships',
        db_index=True
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='tenant_memberships',
        db_index=True
    )
    roles = models.ManyToManyField(
        Role,
        through='MembershipRole',
        related_name='memberships',
        blank=True
    )
    status = models.CharField(
        max_length=20,
        choices=MembershipStatus.choices,
        default=MembershipStatus.ACTIVE,
        db_index=True
    )
    joined_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        verbose_name = 'Tenant Membership'
        verbose_name_plural = 'Tenant Memberships'
        unique_together = ('tenant', 'user')
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['user', 'status']),
        ]

    def __str__(self):
        return f"{self.user.email} in {self.tenant.slug} ({self.status})"

    def has_role(self, role_slug: str) -> bool:
        return self.roles.filter(slug=role_slug).exists()

    def has_permission(self, codename: str) -> bool:
        if self.status != MembershipStatus.ACTIVE:
            return False
        return self.roles.filter(permissions__codename=codename).exists()

    @property
    def is_admin(self) -> bool:
        if self.status != MembershipStatus.ACTIVE:
            return False
        return self.roles.filter(slug__in=['institution_owner', 'institution_admin']).exists()


class MembershipRole(models.Model):
    """
    Through table linking TenantMembership to Roles.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    membership = models.ForeignKey(TenantMembership, on_delete=models.CASCADE, related_name='membership_roles')
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='role_memberships')
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Membership Role'
        verbose_name_plural = 'Membership Roles'
        unique_together = ('membership', 'role')

    def __str__(self):
        return f"{self.membership.user.email} as {self.role.slug}"


class InvitationStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    ACCEPTED = 'accepted', 'Accepted'
    REVOKED = 'revoked', 'Revoked'
    EXPIRED = 'expired', 'Expired'


def default_invitation_expiry():
    return timezone.now() + timedelta(days=7)


def generate_invitation_token():
    return secrets.token_urlsafe(32)


class StaffInvitation(models.Model):
    """
    Cryptographically secure staff and faculty invitations into a Tenant.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='invitations',
        db_index=True
    )
    email = models.EmailField(db_index=True)
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name='invitations'
    )
    token = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        default=generate_invitation_token
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='sent_invitations'
    )
    status = models.CharField(
        max_length=20,
        choices=InvitationStatus.choices,
        default=InvitationStatus.PENDING,
        db_index=True
    )
    expires_at = models.DateTimeField(default=default_invitation_expiry)
    accepted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = TenantManager()

    class Meta:
        verbose_name = 'Staff Invitation'
        verbose_name_plural = 'Staff Invitations'
        indexes = [
            models.Index(fields=['tenant', 'email', 'status']),
        ]

    def __str__(self):
        return f"Invite for {self.email} -> {self.tenant.slug} ({self.role.slug})"

    @property
    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at

    @property
    def is_valid(self) -> bool:
        return self.status == InvitationStatus.PENDING and not self.is_expired

    def accept(self, user):
        """
        Accept invitation, create/activate membership, assign role.
        """
        if not self.is_valid:
            if self.is_expired and self.status == InvitationStatus.PENDING:
                self.status = InvitationStatus.EXPIRED
                self.save(update_fields=['status'])
            raise ValueError("Invitation is no longer valid or has expired.")

        membership, _ = TenantMembership.objects.get_or_create(
            tenant=self.tenant,
            user=user,
            defaults={'status': MembershipStatus.ACTIVE}
        )
        if membership.status != MembershipStatus.ACTIVE:
            membership.status = MembershipStatus.ACTIVE
            membership.save(update_fields=['status'])

        MembershipRole.objects.get_or_create(membership=membership, role=self.role)

        self.status = InvitationStatus.ACCEPTED
        self.accepted_at = timezone.now()
        self.save(update_fields=['status', 'accepted_at'])
        return membership
