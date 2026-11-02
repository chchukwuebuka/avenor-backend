from datetime import date
from django.test import TestCase
from apps.tenants.models import Tenant
from apps.courses.models import (
    Programme,
    Course,
    Module,
    Lesson,
    CourseOffering,
    AcademicStatus,
    CourseLevel,
    DeliveryMode,
    LessonType,
)


class CourseModelTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="Horizon University",
            slug="horizon",
            contact_email="admin@horizon.edu"
        )
        self.prog = Programme.objects.create(
            tenant=self.tenant,
            name="Business Analytics",
            slug="business-analytics",
            status=AcademicStatus.PUBLISHED
        )

    def test_course_creation_and_uniqueness(self):
        course = Course.objects.create(
            tenant=self.tenant,
            programme=self.prog,
            title="Strategic Data Analytics",
            slug="strategic-data-analytics",
            short_description="Executive data analysis course",
            level=CourseLevel.INTERMEDIATE,
            status=AcademicStatus.PUBLISHED
        )
        self.assertEqual(course.tenant, self.tenant)
        self.assertEqual(course.programme, self.prog)

        # Uniqueness per tenant
        with self.assertRaises(Exception):
            Course.objects.create(
                tenant=self.tenant,
                programme=self.prog,
                title="Strategic Data Analytics Duplicate",
                slug="strategic-data-analytics",
                short_description="Duplicate slug"
            )

    def test_module_and_lesson_ordering(self):
        course = Course.objects.create(
            tenant=self.tenant,
            programme=self.prog,
            title="Python for Business",
            slug="python-business",
            short_description="Python course"
        )
        m1 = Module.objects.create(tenant=self.tenant, course=course, title="Module 1", order=1)
        m2 = Module.objects.create(tenant=self.tenant, course=course, title="Module 2", order=2)

        l1 = Lesson.objects.create(tenant=self.tenant, module=m1, title="Intro", order=1, duration_minutes=30)
        l2 = Lesson.objects.create(tenant=self.tenant, module=m1, title="Syntax", order=2, duration_minutes=45)

        self.assertEqual(list(course.modules.all()), [m1, m2])
        self.assertEqual(list(m1.lessons.all()), [l1, l2])

    def test_course_offering_creation(self):
        course = Course.objects.create(
            tenant=self.tenant,
            title="Marketing Strategy",
            slug="marketing-strategy",
            short_description="Marketing course"
        )
        cohort = CourseOffering.objects.create(
            tenant=self.tenant,
            course=course,
            offering_code="MKT-2026-Q1",
            cohort_name="Q1 Intake",
            start_date=date(2026, 4, 1),
            end_date=date(2026, 6, 1),
            price=950.00,
            currency="USD",
            delivery_mode=DeliveryMode.ONLINE
        )
        self.assertEqual(cohort.price, 950.00)
        self.assertEqual(cohort.status, 'open')
