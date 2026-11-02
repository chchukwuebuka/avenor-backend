from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from apps.tenants.models import Tenant
from apps.memberships.models import (
    Permission,
    Role,
    RolePermission,
    TenantMembership,
    MembershipRole,
    MembershipStatus,
)
from common.permissions import (
    IsPlatformOwner,
    IsTenantMember,
    IsTenantAdmin,
    HasTenantPermission,
)

User = get_user_model()


class PermissionClassTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.tenant = Tenant.objects.create(name="Alpha University", slug="alpha-uni", contact_email="admin@alpha.edu")
        self.other_tenant = Tenant.objects.create(name="Beta Institute", slug="beta-inst", contact_email="admin@beta.edu")

        self.superuser = User.objects.create_superuser(
            email="super@avenor.com",
            password="SuperPassword123!"
        )
        self.platform_staff = User.objects.create_user(
            email="staff@avenor.com",
            password="StaffPassword123!",
            is_platform_staff=True
        )
        self.regular_user = User.objects.create_user(
            email="regular@alpha.edu",
            password="RegularPassword123!"
        )
        self.instructor_user = User.objects.create_user(
            email="instructor@alpha.edu",
            password="InstructorPassword123!"
        )

        # Create roles and permissions
        self.perm_courses_publish = Permission.objects.create(
            codename="courses.publish",
            name="Publish Courses",
            module="courses"
        )
        self.role_admin = Role.objects.create(
            slug="institution_admin",
            name="Institution Admin"
        )
        self.role_instructor = Role.objects.create(
            slug="instructor",
            name="Instructor"
        )
        RolePermission.objects.create(role=self.role_admin, permission=self.perm_courses_publish)

        # Assign memberships
        self.membership_admin = TenantMembership.objects.create(
            tenant=self.tenant,
            user=self.regular_user,
            status=MembershipStatus.ACTIVE
        )
        MembershipRole.objects.create(membership=self.membership_admin, role=self.role_admin)

        self.membership_instructor = TenantMembership.objects.create(
            tenant=self.tenant,
            user=self.instructor_user,
            status=MembershipStatus.ACTIVE
        )
        MembershipRole.objects.create(membership=self.membership_instructor, role=self.role_instructor)

    def test_is_platform_owner(self):
        perm = IsPlatformOwner()
        
        req = self.factory.get('/')
        req.user = self.superuser
        self.assertTrue(perm.has_permission(req, None))

        req.user = self.platform_staff
        self.assertTrue(perm.has_permission(req, None))

        req.user = self.regular_user
        self.assertFalse(perm.has_permission(req, None))

    def test_is_tenant_member(self):
        perm = IsTenantMember()

        # Regular user accessing their tenant
        req = self.factory.get('/')
        req.user = self.regular_user
        req.tenant = self.tenant
        self.assertTrue(perm.has_permission(req, None))
        self.assertEqual(req.membership, self.membership_admin)

        # Regular user accessing a different tenant
        req.tenant = self.other_tenant
        req.membership = None
        self.assertFalse(perm.has_permission(req, None))

    def test_is_tenant_admin(self):
        perm = IsTenantAdmin()

        # Institution admin accessing their tenant
        req = self.factory.get('/')
        req.user = self.regular_user
        req.tenant = self.tenant
        self.assertTrue(perm.has_permission(req, None))

        # Instructor accessing their tenant
        req.user = self.instructor_user
        self.assertFalse(perm.has_permission(req, None))

    def test_has_tenant_permission(self):
        perm = HasTenantPermission.with_perm('courses.publish')()

        # Institution admin has courses.publish
        req = self.factory.get('/')
        req.user = self.regular_user
        req.tenant = self.tenant
        self.assertTrue(perm.has_permission(req, None))

        # Instructor does NOT have courses.publish
        req.user = self.instructor_user
        req.membership = None
        self.assertFalse(perm.has_permission(req, None))
