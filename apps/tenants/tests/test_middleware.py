from django.test import TestCase, RequestFactory
from django.urls import reverse
from rest_framework import status
from apps.tenants.models import Tenant, TenantDomain, TenantBranding, TenantStatus
from apps.tenants.middleware import TenantResolutionMiddleware

class TenantMiddlewareTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = TenantResolutionMiddleware(get_response=lambda r: None)

        self.tenant = Tenant.objects.create(
            name='Midland University',
            slug='midland',
            status=TenantStatus.ACTIVE,
            contact_email='admin@midland.edu'
        )
        self.domain = TenantDomain.objects.create(
            tenant=self.tenant,
            hostname='midland.avenor.local',
            is_primary=True,
            is_verified=True
        )

    def test_hostname_resolves_active_tenant(self):
        request = self.factory.get('/api/v1/courses/', HTTP_HOST='midland.avenor.local:8000')
        self.middleware.process_request(request)
        self.assertIsNotNone(request.tenant)
        self.assertEqual(request.tenant.slug, 'midland')

    def test_dev_header_resolves_tenant_in_dev_mode(self):
        request = self.factory.get('/api/v1/courses/', HTTP_HOST='localhost:8000', HTTP_X_DEV_TENANT_DOMAIN='midland.avenor.local')
        self.middleware.process_request(request)
        self.assertIsNotNone(request.tenant)
        self.assertEqual(request.tenant.slug, 'midland')

    def test_suspended_tenant_returns_403(self):
        self.tenant.status = TenantStatus.SUSPENDED
        self.tenant.save()

        request = self.factory.get('/api/v1/courses/', HTTP_HOST='midland.avenor.local')
        response = self.middleware.process_request(request)
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
