import uuid
from django.test import TestCase
from apps.tenants.models import Tenant, TenantDomain, TenantBranding, TenantSettings, InstitutionType, TenantStatus

class TenantModelTests(TestCase):
    def test_create_tenant_successful(self):
        tenant = Tenant.objects.create(
            name='Global Polytechnic',
            slug='global-poly',
            institution_type=InstitutionType.POLYTECHNIC,
            contact_email='info@globalpoly.edu'
        )
        self.assertIsInstance(tenant.id, uuid.UUID)
        self.assertEqual(tenant.status, TenantStatus.ACTIVE)
        self.assertEqual(tenant.default_currency, 'USD')

    def test_primary_domain_uniqueness_per_tenant(self):
        tenant = Tenant.objects.create(
            name='Test Institute',
            slug='test-inst',
            contact_email='contact@testinst.org'
        )
        d1 = TenantDomain.objects.create(
            tenant=tenant,
            hostname='test1.avenor.local',
            is_primary=True,
            is_verified=True
        )
        d2 = TenantDomain.objects.create(
            tenant=tenant,
            hostname='test2.avenor.local',
            is_primary=True,
            is_verified=True
        )

        d1.refresh_from_db()
        self.assertFalse(d1.is_primary)
        self.assertTrue(d2.is_primary)

    def test_tenant_branding_creation(self):
        tenant = Tenant.objects.create(
            name='Branded Academy',
            slug='branded-academy',
            contact_email='branding@test.org'
        )
        branding = TenantBranding.objects.create(
            tenant=tenant,
            site_name='Branded Academy',
            primary_colour='#222222',
            accent_colour='#2563EB'
        )
        self.assertEqual(branding.primary_colour, '#222222')
        self.assertEqual(branding.heading_font, 'Sora')
        self.assertEqual(branding.body_font, 'Manrope')
