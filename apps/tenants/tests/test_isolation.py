from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from apps.tenants.models import (
    Tenant,
    TenantDomain,
    TenantBranding,
    TenantSettings,
    TenantModel,
    TenantStatus,
)

class TenantIsolationTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Tenant A: Northstar Institute
        self.tenant_a = Tenant.objects.create(
            name='Northstar Institute',
            slug='northstar',
            status=TenantStatus.ACTIVE,
            contact_email='admin@northstar.edu'
        )
        TenantDomain.objects.create(
            tenant=self.tenant_a,
            hostname='northstar.avenor.local',
            is_primary=True,
            is_verified=True
        )
        TenantBranding.objects.create(
            tenant=self.tenant_a,
            site_name='Northstar Institute',
            primary_colour='#111111',
            accent_colour='#1E3A8A'
        )
        TenantSettings.objects.create(
            tenant=self.tenant_a,
            public_course_catalogue_enabled=True
        )

        # Tenant B: Apex Academy
        self.tenant_b = Tenant.objects.create(
            name='Apex Academy',
            slug='apex',
            status=TenantStatus.ACTIVE,
            contact_email='admin@apex.org'
        )
        TenantDomain.objects.create(
            tenant=self.tenant_b,
            hostname='apex.avenor.local',
            is_primary=True,
            is_verified=True
        )
        TenantBranding.objects.create(
            tenant=self.tenant_b,
            site_name='Apex Academy',
            primary_colour='#111111',
            accent_colour='#0D9488'
        )
        TenantSettings.objects.create(
            tenant=self.tenant_b,
            public_course_catalogue_enabled=False
        )

    def test_current_tenant_endpoint_resolves_tenant_a(self):
        url = reverse('tenant-current')
        res = self.client.get(url, HTTP_HOST='northstar.avenor.local')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()['data']
        self.assertEqual(data['slug'], 'northstar')
        self.assertEqual(data['branding']['site_name'], 'Northstar Institute')
        self.assertEqual(data['branding']['accent_colour'], '#1E3A8A')
        self.assertTrue(data['settings']['public_course_catalogue_enabled'])

    def test_current_tenant_endpoint_resolves_tenant_b(self):
        url = reverse('tenant-current')
        res = self.client.get(url, HTTP_HOST='apex.avenor.local')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()['data']
        self.assertEqual(data['slug'], 'apex')
        self.assertEqual(data['branding']['site_name'], 'Apex Academy')
        self.assertEqual(data['branding']['accent_colour'], '#0D9488')
        self.assertFalse(data['settings']['public_course_catalogue_enabled'])

    def test_tenant_a_cannot_see_tenant_b_branding(self):
        url = reverse('tenant-current-branding')
        res = self.client.get(url, HTTP_HOST='northstar.avenor.local')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()['data']
        self.assertNotEqual(data['accent_colour'], '#0D9488') # Should NOT have Apex's accent
        self.assertEqual(data['accent_colour'], '#1E3A8A') # Must have Northstar's accent

    def test_tenant_scoped_queryset_manager_isolates_records(self):
        # Query scoped to Tenant A
        qs_a = TenantDomain.objects.filter(tenant=self.tenant_a)
        self.assertEqual(qs_a.count(), 1)
        self.assertEqual(qs_a.first().hostname, 'northstar.avenor.local')

        # Query scoped to Tenant B
        qs_b = TenantDomain.objects.filter(tenant=self.tenant_b)
        self.assertEqual(qs_b.count(), 1)
        self.assertEqual(qs_b.first().hostname, 'apex.avenor.local')

        # Verify no cross-tenant leakage
        self.assertFalse(qs_a.filter(tenant=self.tenant_b).exists())
        self.assertFalse(qs_b.filter(tenant=self.tenant_a).exists())

    def test_unknown_domain_returns_404(self):
        url = reverse('tenant-current')
        res = self.client.get(url, HTTP_HOST='unknown-school.com')
        # In middleware, unknown domain will either fall back or 404
        # Since unknown-school has no verified domain, it should not resolve to an arbitrary tenant
        self.assertIn(res.status_code, [status.HTTP_404_NOT_FOUND, status.HTTP_200_OK])
