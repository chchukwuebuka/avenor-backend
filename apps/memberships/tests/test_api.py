from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from apps.tenants.models import Tenant, TenantDomain
from apps.memberships.models import (
    Role,
    TenantMembership,
    MembershipRole,
    StaffInvitation,
    MembershipStatus,
    InvitationStatus,
)

User = get_user_model()


class MembershipAPITests(APITestCase):
    def setUp(self):
        # Create Tenants
        self.tenant_a = Tenant.objects.create(name="Apex Academy", slug="apex", contact_email="admin@apex.edu")
        self.domain_a = TenantDomain.objects.create(tenant=self.tenant_a, hostname="apex.avenor.local", is_verified=True, is_primary=True)

        self.tenant_b = Tenant.objects.create(name="Beacon Institute", slug="beacon", contact_email="admin@beacon.edu")
        self.domain_b = TenantDomain.objects.create(tenant=self.tenant_b, hostname="beacon.avenor.local", is_verified=True, is_primary=True)

        # Create Roles
        self.role_owner = Role.objects.create(slug="institution_owner", name="Institution Owner")
        self.role_admin = Role.objects.create(slug="institution_admin", name="Institution Admin")
        self.role_instructor = Role.objects.create(slug="instructor", name="Instructor")

        # Create Users
        self.admin_user_a = User.objects.create_user(email="admin@apex.edu", password="Password123!", first_name="Apex", last_name="Admin")
        self.instructor_a = User.objects.create_user(email="prof@apex.edu", password="Password123!", first_name="Apex", last_name="Prof")
        self.user_b = User.objects.create_user(email="user@beacon.edu", password="Password123!", first_name="Beacon", last_name="User")

        # Assign Memberships in Tenant A
        self.membership_admin_a = TenantMembership.objects.create(tenant=self.tenant_a, user=self.admin_user_a, status=MembershipStatus.ACTIVE)
        MembershipRole.objects.create(membership=self.membership_admin_a, role=self.role_owner)

        self.membership_prof_a = TenantMembership.objects.create(tenant=self.tenant_a, user=self.instructor_a, status=MembershipStatus.ACTIVE)
        MembershipRole.objects.create(membership=self.membership_prof_a, role=self.role_instructor)

        # Assign Membership in Tenant B
        self.membership_b = TenantMembership.objects.create(tenant=self.tenant_b, user=self.user_b, status=MembershipStatus.ACTIVE)
        MembershipRole.objects.create(membership=self.membership_b, role=self.role_owner)

    def test_member_list_tenant_isolation(self):
        self.client.force_authenticate(user=self.admin_user_a)
        response = self.client.get('/api/v1/members/', HTTP_HOST='apex.avenor.local')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Expected results in paginated data or list
        results = response.data.get('results', response.data)
        emails = [m['user']['email'] for m in results]

        self.assertIn('admin@apex.edu', emails)
        self.assertIn('prof@apex.edu', emails)
        # Ensure Tenant B user is NOT leaked!
        self.assertNotIn('user@beacon.edu', emails)

    def test_member_update_role_and_suspend(self):
        self.client.force_authenticate(user=self.admin_user_a)

        # Update role to institution_admin
        patch_res = self.client.patch(
            f'/api/v1/members/{self.membership_prof_a.id}/',
            {'role_slugs': ['institution_admin']},
            HTTP_HOST='apex.avenor.local',
            format='json'
        )
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)
        self.assertIn('institution_admin', patch_res.data['role_slugs'])

        # Suspend member
        suspend_res = self.client.post(
            f'/api/v1/members/{self.membership_prof_a.id}/suspend/',
            HTTP_HOST='apex.avenor.local'
        )
        self.assertEqual(suspend_res.status_code, status.HTTP_200_OK)
        self.assertEqual(suspend_res.data['status'], 'suspended')

        # Reactivate member
        reactivate_res = self.client.post(
            f'/api/v1/members/{self.membership_prof_a.id}/reactivate/',
            HTTP_HOST='apex.avenor.local'
        )
        self.assertEqual(reactivate_res.status_code, status.HTTP_200_OK)
        self.assertEqual(reactivate_res.data['status'], 'active')

    def test_staff_invitation_flow(self):
        self.client.force_authenticate(user=self.admin_user_a)

        # 1. Send invitation
        invite_res = self.client.post(
            '/api/v1/members/invitations/',
            {'email': 'newfaculty@apex.edu', 'role_slug': 'instructor'},
            HTTP_HOST='apex.avenor.local',
            format='json'
        )
        self.assertEqual(invite_res.status_code, status.HTTP_201_CREATED)
        token = invite_res.data['token']
        self.assertTrue(token)

        # 2. Accept invitation (public endpoint)
        self.client.force_authenticate(user=None)
        accept_res = self.client.post(
            f'/api/v1/members/invitations/{token}/accept/',
            {
                'password': 'BrandNewPassword123!',
                'first_name': 'New',
                'last_name': 'Faculty'
            },
            HTTP_HOST='apex.avenor.local',
            format='json'
        )
        self.assertEqual(accept_res.status_code, status.HTTP_200_OK)

        # Verify new user created and joined Apex Academy
        new_faculty = User.objects.get(email='newfaculty@apex.edu')
        self.assertTrue(new_faculty.check_password('BrandNewPassword123!'))
        self.assertTrue(
            TenantMembership.objects.filter(
                tenant=self.tenant_a,
                user=new_faculty,
                status=MembershipStatus.ACTIVE
            ).exists()
        )

    def test_staff_invitation_revoke(self):
        self.client.force_authenticate(user=self.admin_user_a)

        invitation = StaffInvitation.objects.create(
            tenant=self.tenant_a,
            email="to_revoke@apex.edu",
            role=self.role_instructor,
            invited_by=self.admin_user_a
        )

        res = self.client.post(
            f'/api/v1/members/invitations/{invitation.id}/revoke/',
            HTTP_HOST='apex.avenor.local'
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, InvitationStatus.REVOKED)

    def test_jwt_logout_blacklists_token(self):
        refresh = RefreshToken.for_user(self.admin_user_a)
        access_token = str(refresh.access_token)

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        logout_res = self.client.post('/api/v1/auth/logout/', {'refresh': str(refresh)}, format='json')
        self.assertEqual(logout_res.status_code, status.HTTP_200_OK)

        # Refreshing using the blacklisted refresh token should now fail
        refresh_res = self.client.post('/api/v1/auth/token/refresh/', {'refresh': str(refresh)}, format='json')
        self.assertEqual(refresh_res.status_code, status.HTTP_401_UNAUTHORIZED)
