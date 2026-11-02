import uuid
from datetime import timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.tenants.models import Tenant
from apps.memberships.models import (
    Permission,
    Role,
    RolePermission,
    TenantMembership,
    MembershipRole,
    StaffInvitation,
    MembershipStatus,
    InvitationStatus,
)

User = get_user_model()


class MembershipModelTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="Test Academy",
            slug="test-academy",
            contact_email="admin@testacademy.edu"
        )
        self.user = User.objects.create_user(
            email="faculty@testacademy.edu",
            password="SecurePassword123!",
            first_name="Jane",
            last_name="Doe"
        )
        self.perm_courses_create = Permission.objects.create(
            codename="courses.create",
            name="Create Courses",
            module="courses"
        )
        self.perm_courses_view = Permission.objects.create(
            codename="courses.view",
            name="View Courses",
            module="courses"
        )
        self.role_instructor = Role.objects.create(
            slug="instructor",
            name="Instructor",
            is_platform_role=False
        )
        RolePermission.objects.create(role=self.role_instructor, permission=self.perm_courses_create)
        RolePermission.objects.create(role=self.role_instructor, permission=self.perm_courses_view)

    def test_role_and_permissions(self):
        self.assertEqual(self.role_instructor.permissions.count(), 2)
        self.assertTrue(self.role_instructor.permissions.filter(codename="courses.create").exists())

    def test_tenant_membership_creation(self):
        membership = TenantMembership.objects.create(
            tenant=self.tenant,
            user=self.user,
            status=MembershipStatus.ACTIVE
        )
        MembershipRole.objects.create(membership=membership, role=self.role_instructor)

        self.assertTrue(membership.has_role("instructor"))
        self.assertFalse(membership.has_role("institution_admin"))
        self.assertTrue(membership.has_permission("courses.create"))
        self.assertFalse(membership.has_permission("billing.manage"))

    def test_membership_uniqueness(self):
        TenantMembership.objects.create(
            tenant=self.tenant,
            user=self.user,
            status=MembershipStatus.ACTIVE
        )
        with self.assertRaises(Exception):
            TenantMembership.objects.create(
                tenant=self.tenant,
                user=self.user,
                status=MembershipStatus.ACTIVE
            )

    def test_staff_invitation_lifecycle(self):
        invitation = StaffInvitation.objects.create(
            tenant=self.tenant,
            email="newhire@testacademy.edu",
            role=self.role_instructor,
            invited_by=self.user
        )
        self.assertTrue(invitation.is_valid)
        self.assertEqual(invitation.status, InvitationStatus.PENDING)

        new_user = User.objects.create_user(
            email="newhire@testacademy.edu",
            password="SecurePassword123!"
        )
        membership = invitation.accept(new_user)

        self.assertEqual(invitation.status, InvitationStatus.ACCEPTED)
        self.assertIsNotNone(invitation.accepted_at)
        self.assertTrue(membership.has_role("instructor"))
        self.assertEqual(membership.status, MembershipStatus.ACTIVE)

    def test_expired_invitation_cannot_be_accepted(self):
        invitation = StaffInvitation.objects.create(
            tenant=self.tenant,
            email="expired@testacademy.edu",
            role=self.role_instructor,
            invited_by=self.user,
            expires_at=timezone.now() - timedelta(days=1)
        )
        self.assertFalse(invitation.is_valid)
        self.assertTrue(invitation.is_expired)

        new_user = User.objects.create_user(
            email="expired@testacademy.edu",
            password="SecurePassword123!"
        )
        with self.assertRaises(ValueError):
            invitation.accept(new_user)
