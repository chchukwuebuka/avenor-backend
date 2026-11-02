from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status
from apps.tenants.models import Tenant, TenantDomain, TenantStatus

User = get_user_model()


class PlatformFleetAPITests(APITestCase):
    def setUp(self):
        self.super_user = User.objects.create_superuser(
            email="platform@avenor.com",
            password="PlatformPassword123!"
        )
        self.regular_user = User.objects.create_user(
            email="regular@user.com",
            password="RegularPassword123!"
        )
        self.tenant = Tenant.objects.create(
            name="Cambridge Academy",
            slug="cambridge",
            contact_email="admin@cambridge.ac.uk",
            status=TenantStatus.ACTIVE
        )
        self.domain = TenantDomain.objects.create(
            tenant=self.tenant,
            hostname="cambridge.avenor.local",
            is_primary=True,
            is_verified=True
        )

    def test_fleet_list_requires_platform_owner(self):
        self.client.force_authenticate(user=self.regular_user)
        res = self.client.get('/api/v1/tenants/')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.super_user)
        res = self.client.get('/api/v1/tenants/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['count'], 1)
        self.assertEqual(res.data['data'][0]['slug'], 'cambridge')

    def test_tenant_provisioning_flow(self):
        self.client.force_authenticate(user=self.super_user)
        payload = {
            'name': 'Oxford Polytechnic Institute',
            'slug': 'oxford-poly',
            'institution_type': 'polytechnic',
            'contact_email': 'contact@oxfordpoly.ac.uk',
            'primary_domain': 'oxford.avenor.local',
            'accent_colour': '#2563EB',
            'default_currency': 'GBP',
            'timezone': 'Europe/London',
        }
        res = self.client.post('/api/v1/tenants/', payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data['success'])
        
        # Verify database entities created
        new_tenant = Tenant.objects.get(slug='oxford-poly')
        self.assertEqual(new_tenant.name, 'Oxford Polytechnic Institute')
        self.assertTrue(new_tenant.domains.filter(hostname='oxford.avenor.local', is_primary=True).exists())
        self.assertTrue(hasattr(new_tenant, 'branding'))
        self.assertEqual(new_tenant.branding.accent_colour, '#2563EB')
        self.assertTrue(hasattr(new_tenant, 'settings'))
        self.assertTrue(new_tenant.settings.public_registration_enabled)

    def test_tenant_status_update(self):
        self.client.force_authenticate(user=self.super_user)
        patch_res = self.client.patch(
            f'/api/v1/tenants/{self.tenant.id}/',
            {'status': 'suspended'},
            format='json'
        )
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)
        self.tenant.refresh_from_db()
        self.assertEqual(self.tenant.status, TenantStatus.SUSPENDED)

    def test_platform_fleet_stats(self):
        self.client.force_authenticate(user=self.super_user)
        res = self.client.get('/api/v1/tenants/stats/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['data']['tenants']['total'], 1)
        self.assertEqual(res.data['data']['system']['status'], 'operational')
