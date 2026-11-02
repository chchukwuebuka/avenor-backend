from datetime import date
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from apps.tenants.models import Tenant, TenantDomain
from apps.courses.models import (
    Programme,
    Course,
    Module,
    Lesson,
    CourseOffering,
    AcademicStatus,
    CourseLevel,
    DeliveryMode,
)


class PublicCourseAPITests(APITestCase):
    def setUp(self):
        # Tenant A
        self.tenant_a = Tenant.objects.create(name="Alpha Institute", slug="alpha", contact_email="admin@alpha.edu")
        self.domain_a = TenantDomain.objects.create(tenant=self.tenant_a, hostname="alpha.avenor.local", is_primary=True, is_verified=True)

        # Tenant B
        self.tenant_b = Tenant.objects.create(name="Beta Academy", slug="beta", contact_email="admin@beta.edu")
        self.domain_b = TenantDomain.objects.create(tenant=self.tenant_b, hostname="beta.avenor.local", is_primary=True, is_verified=True)

        # Programmes
        self.prog_a = Programme.objects.create(tenant=self.tenant_a, name="Executive Management", slug="exec-mgmt", status=AcademicStatus.PUBLISHED)
        self.prog_b = Programme.objects.create(tenant=self.tenant_b, name="Creative Design", slug="design", status=AcademicStatus.PUBLISHED)

        # Published Course in Tenant A
        self.course_a_pub = Course.objects.create(
            tenant=self.tenant_a,
            programme=self.prog_a,
            title="Strategic Leadership",
            slug="strategic-leadership",
            short_description="Executive leadership course",
            level=CourseLevel.ADVANCED,
            status=AcademicStatus.PUBLISHED
        )
        self.cohort_a = CourseOffering.objects.create(
            tenant=self.tenant_a,
            course=self.course_a_pub,
            offering_code="ALPHA-STRAT-26",
            cohort_name="Spring 2026",
            start_date=date(2026, 3, 1),
            end_date=date(2026, 5, 1),
            price=1200.00,
            currency="USD",
            delivery_mode=DeliveryMode.HYBRID
        )

        # Draft Course in Tenant A (must NOT appear publicly)
        self.course_a_draft = Course.objects.create(
            tenant=self.tenant_a,
            title="Unpublished Draft Course",
            slug="unpublished-draft",
            short_description="Work in progress",
            status=AcademicStatus.DRAFT
        )

        # Published Course in Tenant B (must NOT leak into Tenant A)
        self.course_b_pub = Course.objects.create(
            tenant=self.tenant_b,
            programme=self.prog_b,
            title="Graphic Design Masterclass",
            slug="graphic-design",
            short_description="Design course",
            status=AcademicStatus.PUBLISHED
        )

    def test_public_course_list_tenant_isolation(self):
        # Query Tenant A public catalogue
        res = self.client.get('/api/v1/courses/', HTTP_HOST='alpha.avenor.local')
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        results = res.data.get('results', res.data)
        slugs = [c['slug'] for c in results]

        # Strategic Leadership should be present
        self.assertIn('strategic-leadership', slugs)
        # Draft course should NOT be present
        self.assertNotIn('unpublished-draft', slugs)
        # Tenant B course should NOT be present
        self.assertNotIn('graphic-design', slugs)

    def test_public_course_filtering_by_level(self):
        res = self.client.get('/api/v1/courses/?level=advanced', HTTP_HOST='alpha.avenor.local')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        results = res.data.get('results', res.data)
        self.assertEqual(len(results), 1)

        res_none = self.client.get('/api/v1/courses/?level=beginner', HTTP_HOST='alpha.avenor.local')
        results_none = res_none.data.get('results', res_none.data)
        self.assertEqual(len(results_none), 0)

    def test_public_course_detail(self):
        res = self.client.get('/api/v1/courses/strategic-leadership/', HTTP_HOST='alpha.avenor.local')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['data']['title'], 'Strategic Leadership')
        self.assertEqual(len(res.data['data']['offerings']), 1)

        # Draft course detail should return 404
        res_draft = self.client.get('/api/v1/courses/unpublished-draft/', HTTP_HOST='alpha.avenor.local')
        self.assertEqual(res_draft.status_code, status.HTTP_404_NOT_FOUND)

    def test_public_programme_list(self):
        res = self.client.get('/api/v1/courses/programmes/', HTTP_HOST='alpha.avenor.local')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        results = res.data.get('results', res.data)
        slugs = [p['slug'] for p in results]
        self.assertIn('exec-mgmt', slugs)
        self.assertNotIn('design', slugs)
